// @vitest-environment node
/**
 * scripts/claude ラッパの拡張選択ロジックのスモークテスト。
 *
 * fake $HOME に VSCode 拡張ディレクトリ + 実行可能 stub バイナリを作り、
 * PATH の先頭に置いた偽の uname で実行環境を固定したうえで
 * `sh scripts/claude ...` を spawn して以下を pin する:
 *   1. platform 完全一致の複数 version から sort -V で最高 version を選ぶ
 *   2. 完全一致ゼロ + 他 suffix 拡張ありなら任意 platform の最新版へフォールバック
 *   3. 拡張ゼロなら exit 1 + stderr に not found と platform 名
 *   4. wrapper フラグ (--no-bypass / --no-ctx) は剥がされ本体へ渡らない
 *
 * 実行環境は偽の uname が決めるので、検体を走らせた開発機の
 * process.platform / process.arch は結果に影響しない (lctl 正典 t1 の i7)。
 *
 * 実行: pnpm test (vitest の include に scripts/**\/*.test.ts が含まれる)
 */
import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const REPO_ROOT = join(__dirname, "..");
const WRAPPER = join(REPO_ROOT, "scripts", "claude");

type Platform = {
    /** 偽の uname -s の答え */
    unameS: string;
    /** 偽の uname -m の答え */
    unameM: string;
    /** scripts/claude が上の 2 つから導く拡張ディレクトリの接尾辞 */
    extSuffix: string;
};

/** 検体が使う唯一の実行環境。写像の全数は回さない (主張を増やさないため)。 */
const LINUX_ARM64: Platform = {
    unameS: "Linux",
    unameM: "aarch64",
    extSuffix: "linux-arm64",
};

/** 上と必ず異なる接尾辞 (フォールバック経路の検体で使う)。 */
const OTHER_SUFFIX = "darwin-x64";

/**
 * PATH の先頭に置く偽の実行ファイルの置き場を作る。
 * 作るのは uname だけで、ls / sed / sort / tail は実 PATH のものを使う。
 */
function fakeBinDir(platform: Platform): string {
    const dir = mkdtempSync(join(tmpdir(), "claude-wrapper-bin-"));
    const uname = join(dir, "uname");
    writeFileSync(
        uname,
        `#!/bin/sh\ncase "$1" in\n  -s) echo ${platform.unameS} ;;\n  -m) echo ${platform.unameM} ;;\n  *) echo ${platform.unameS} ;;\nesac\n`,
    );
    chmodSync(uname, 0o755);
    return dir;
}

/** fake HOME 配下に拡張ディレクトリ + stub バイナリを作る */
function installExtension(
    home: string,
    root: ".vscode" | ".vscode-server",
    versionSuffix: string,
): string {
    const extDir = join(
        home,
        root,
        "extensions",
        `anthropic.claude-code-${versionSuffix}`,
    );
    const binDir = join(extDir, "resources", "native-binary");
    mkdirSync(binDir, { recursive: true });
    const bin = join(binDir, "claude");
    // 自身のパスと argv を印字して即終了する stub
    writeFileSync(
        bin,
        '#!/bin/sh\necho "STUB_PATH=$0"\nfor a in "$@"; do echo "ARG=$a"; done\n',
    );
    chmodSync(bin, 0o755);
    return bin;
}

type RunResult = { status: number; stdout: string; stderr: string };

/** ラッパを起こす。実 PATH を継承したうえで偽の uname の置き場を前置する。 */
function runWrapper(
    home: string,
    args: string[] = [],
    platform: Platform = LINUX_ARM64,
): RunResult {
    // execFileSync は成功時に stderr を返さないため spawnSync で両 stream を捕捉する
    const result = spawnSync("sh", [WRAPPER, ...args], {
        env: {
            ...process.env,
            HOME: home,
            PATH: `${fakeBinDir(platform)}:${process.env.PATH ?? ""}`,
        },
        cwd: REPO_ROOT,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
    });
    return {
        status: result.status ?? -1,
        stdout: result.stdout,
        stderr: result.stderr,
    };
}

describe("scripts/claude — 拡張選択", () => {
    it("platform 完全一致の複数 version から最高 version を選ぶ (sort -V、両 root 横断)", () => {
        const home = mkdtempSync(join(tmpdir(), "claude-wrapper-"));
        const platform = LINUX_ARM64.extSuffix;
        installExtension(home, ".vscode", `1.0.9-${platform}`);
        // 1.0.10 は辞書順では 1.0.9 より前に来るため sort -V の検証になる
        installExtension(home, ".vscode-server", `1.0.10-${platform}`);

        const result = runWrapper(home, ["--no-ctx", "--no-bypass"]);
        expect(result.status).toBe(0);
        expect(result.stdout).toContain(
            `anthropic.claude-code-1.0.10-${platform}`,
        );
    });

    it("完全一致ゼロ + 他 suffix 拡張ありなら任意 platform の最新版へフォールバックする", () => {
        const home = mkdtempSync(join(tmpdir(), "claude-wrapper-"));
        // 偽の uname が答える実行環境と必ず異なる suffix を置く
        installExtension(home, ".vscode", `2.1.0-${OTHER_SUFFIX}`);
        installExtension(home, ".vscode", `2.0.0-${OTHER_SUFFIX}`);

        const result = runWrapper(home, ["--no-ctx", "--no-bypass"]);
        expect(result.status).toBe(0);
        expect(result.stdout).toContain(
            `anthropic.claude-code-2.1.0-${OTHER_SUFFIX}`,
        );
        // フォールバックは silent ではなく stderr へ warning を出す (調査性のため)。
        // 文言には依存させない (設計裁定) — 存在のみを pin する。
        expect(result.stderr).not.toBe("");
    });

    it("platform 完全一致があれば他 suffix の方が新 version でも exact を優先する", () => {
        const home = mkdtempSync(join(tmpdir(), "claude-wrapper-"));
        const platform = LINUX_ARM64.extSuffix;
        installExtension(home, ".vscode", `1.0.0-${platform}`);
        installExtension(home, ".vscode", `9.9.9-${OTHER_SUFFIX}`);

        const result = runWrapper(home, ["--no-ctx", "--no-bypass"]);
        expect(result.status).toBe(0);
        expect(result.stdout).toContain(
            `anthropic.claude-code-1.0.0-${platform}`,
        );
        // exact 一致経路ではフォールバック warning は出ない
        expect(result.stderr).toBe("");
    });

    it("拡張ゼロなら exit 1 + stderr に not found と検出 platform 名", () => {
        const home = mkdtempSync(join(tmpdir(), "claude-wrapper-"));
        const result = runWrapper(home, ["--no-ctx", "--no-bypass"]);
        expect(result.status).toBe(1);
        expect(result.stderr).toMatch(/not found/i);
        expect(result.stderr).toContain(
            `platform: ${LINUX_ARM64.extSuffix}`,
        );
    });
});

describe("scripts/claude — wrapper フラグ規約", () => {
    it("--no-ctx のみでは --dangerously-skip-permissions が argv 先頭に付く", () => {
        const home = mkdtempSync(join(tmpdir(), "claude-wrapper-"));
        installExtension(home, ".vscode", `1.0.0-${LINUX_ARM64.extSuffix}`);

        const result = runWrapper(home, ["--no-ctx"]);
        expect(result.status).toBe(0);
        const args = result.stdout
            .split("\n")
            .filter((line) => line.startsWith("ARG="))
            .map((line) => line.slice("ARG=".length));
        expect(args[0]).toBe("--dangerously-skip-permissions");
    });

    it("--no-ctx --no-bypass extra では wrapper フラグが剥がされ argv は extra のみ", () => {
        const home = mkdtempSync(join(tmpdir(), "claude-wrapper-"));
        installExtension(home, ".vscode", `1.0.0-${LINUX_ARM64.extSuffix}`);

        const result = runWrapper(home, ["--no-ctx", "--no-bypass", "extra"]);
        expect(result.status).toBe(0);
        const args = result.stdout
            .split("\n")
            .filter((line) => line.startsWith("ARG="))
            .map((line) => line.slice("ARG=".length));
        expect(args).toEqual(["extra"]);
    });
});
