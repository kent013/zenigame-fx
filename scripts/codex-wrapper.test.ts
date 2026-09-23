// @vitest-environment node
/**
 * scripts/codex ラッパの探索の回帰テスト
 * (lctl feature vscode-cli-wrappers の正典 t1。i1 / i2 / i3 / i4 / i5 を i7 の求めに従って固定する)。
 *
 * 固定するのは観測できる振る舞いだけである — どの実行ファイルが起動したか / 引数が変えられずに
 * 届くか / 終了コードが返るか / 見つからないときに何を言うか。実装の内部 (変数名・関数の分割) は見ない。
 *
 * 実行環境は uname を PATH の先頭で差し替えて検体の側が決める (i7)。走らせた開発機の実行環境が
 * 結果を決めない。
 *
 * 文言の逐語一致は使わない。ただし失敗の 2 状態 (i4) を見分けるために、契約として固定する語を
 * 1 つだけ置く。契約の対象はラッパが出す固定の文 (可変のデータを含まない行) に限る。
 *   - 状態 A (名前の当たるディレクトリが 1 つも無い) の案内の行は、小文字の install を含む
 *   - 状態 B (当たったが起動できる現物が無い) の固定の文は、大文字と小文字を問わず install を含まない
 * 候補の絶対パス (= ホームの絶対パス) を含む行は判定から除く。ホームの名前が install を含む場合と
 * 衝突させないためである (検体 D4)。この契約は scripts/README.md にも同じ形で書いてある。
 *
 * 実行: pnpm test (vitest の include に scripts/ 配下の *.test.ts が含まれる)
 */
import { afterEach, describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import {
    chmodSync,
    mkdirSync,
    mkdtempSync,
    rmSync,
    writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

const REPO_ROOT = join(__dirname, "..");
const WRAPPER = join(REPO_ROOT, "scripts", "codex");

/** 外した理由の語彙は 2 種類だけである (i4)。 */
const REASON_VERSION = "not a readable version in the directory name";
const REASON_BINARY = "no runnable binary for this platform";

/**
 * 検体が決める実行環境。
 * binRel は同梱物の中の下位ディレクトリの綴り、extSuffix は拡張のディレクトリ名の接尾辞
 * (現物の実装が候補の必要条件にしていた語彙。既定の名前の作り方に使う)。
 */
type Platform = {
    unameS: string;
    unameM: string;
    binRel: string;
    extSuffix: string;
};

const LINUX_ARM64: Platform = {
    unameS: "Linux",
    unameM: "aarch64",
    binRel: "bin/linux-aarch64",
    extSuffix: "linux-arm64",
};

/** M1 の写像が受理する uname の答えの全数 (別名を含む 8 組)。 */
const ACCEPTED_PLATFORMS: Platform[] = [
    {
        unameS: "Linux",
        unameM: "aarch64",
        binRel: "bin/linux-aarch64",
        extSuffix: "linux-arm64",
    },
    {
        unameS: "Linux",
        unameM: "arm64",
        binRel: "bin/linux-aarch64",
        extSuffix: "linux-arm64",
    },
    {
        unameS: "Linux",
        unameM: "x86_64",
        binRel: "bin/linux-x86_64",
        extSuffix: "linux-x64",
    },
    {
        unameS: "Linux",
        unameM: "amd64",
        binRel: "bin/linux-x86_64",
        extSuffix: "linux-x64",
    },
    {
        unameS: "Darwin",
        unameM: "arm64",
        binRel: "bin/macos-aarch64",
        extSuffix: "darwin-arm64",
    },
    {
        unameS: "Darwin",
        unameM: "aarch64",
        binRel: "bin/macos-aarch64",
        extSuffix: "darwin-arm64",
    },
    {
        unameS: "Darwin",
        unameM: "x86_64",
        binRel: "bin/macos-x86_64",
        extSuffix: "darwin-x64",
    },
    {
        unameS: "Darwin",
        unameM: "amd64",
        binRel: "bin/macos-x86_64",
        extSuffix: "darwin-x64",
    },
];

/** 後始末のために作った一時ディレクトリを控える。 */
const createdDirs: string[] = [];

afterEach(() => {
    while (createdDirs.length > 0) {
        const dir = createdDirs.pop();
        if (dir !== undefined) {
            rmSync(dir, { recursive: true, force: true });
        }
    }
});

/** 偽の HOME を作る。 */
function makeHome(prefix = "codex-wrapper-"): string {
    const home = mkdtempSync(join(tmpdir(), prefix));
    createdDirs.push(home);
    return home;
}

type ExtensionOptions = {
    /** 代理の実行ファイルを置く相対ディレクトリ。既定は platform の binRel。 */
    binRel?: string;
    /** 置かない (不在の負例)。 */
    omitBinary?: boolean;
    /** codex を実行ファイルではなくディレクトリとして作る (-x だけでは真になる負例)。 */
    binaryAsDirectory?: boolean;
    /** 実行権を与えない (-f だけでは真になる負例)。 */
    notExecutable?: boolean;
    /** 代理の実行ファイルが返す終了コード。既定は 0。 */
    exitCode?: number;
};

/** 偽の HOME 配下に拡張ディレクトリと代理の実行ファイルを作り、拡張ディレクトリを返す。 */
function installExtension(
    home: string,
    root: ".vscode" | ".vscode-server",
    dirName: string,
    platform: Platform = LINUX_ARM64,
    options: ExtensionOptions = {},
): string {
    const extDir = join(home, root, "extensions", dirName);
    mkdirSync(extDir, { recursive: true });
    if (options.omitBinary === true) {
        return extDir;
    }
    const bin = join(extDir, options.binRel ?? platform.binRel, "codex");
    if (options.binaryAsDirectory === true) {
        mkdirSync(bin, { recursive: true });
        return extDir;
    }
    mkdirSync(dirname(bin), { recursive: true });
    // 自身のパスと argv を印字して指定の終了コードで終わる代理の実行ファイル
    writeFileSync(
        bin,
        `#!/bin/sh\necho "STUB_PATH=$0"\nfor a in "$@"; do echo "ARG=$a"; done\nexit ${options.exitCode ?? 0}\n`,
    );
    chmodSync(bin, options.notExecutable === true ? 0o644 : 0o755);
    return extDir;
}

/** 既定の名前の作り方 (接尾辞つき)。接尾辞を外す件は dirName を直接渡す。 */
function extensionName(
    version: string,
    platform: Platform = LINUX_ARM64,
): string {
    return `openai.chatgpt-${version}-${platform.extSuffix}`;
}

/**
 * PATH の先頭に置く偽の実行ファイルの置き場を作る。
 * uname は必ず置き、breakSort が真なら必ず失敗する sort も置く (検体 E1)。
 */
function fakeBinDir(platform: Platform, breakSort = false): string {
    const dir = mkdtempSync(join(tmpdir(), "codex-wrapper-bin-"));
    createdDirs.push(dir);
    const uname = join(dir, "uname");
    writeFileSync(
        uname,
        `#!/bin/sh\ncase "$1" in\n  -s) echo ${platform.unameS} ;;\n  -m) echo ${platform.unameM} ;;\n  *) echo ${platform.unameS} ;;\nesac\n`,
    );
    chmodSync(uname, 0o755);
    if (breakSort) {
        const sort = join(dir, "sort");
        // 無言で失敗させる。標準エラー出力に何か出ていれば、それはラッパが出した理由である。
        writeFileSync(sort, "#!/bin/sh\nexit 2\n");
        chmodSync(sort, 0o755);
    }
    return dir;
}

type RunOptions = {
    platform?: Platform;
    /** ラッパへ渡す追加の環境変数 (B9 が LC_ALL を差し替える)。 */
    env?: Record<string, string>;
    /** PATH の先頭に必ず失敗する sort を置く (E1)。 */
    breakSort?: boolean;
};

/** ラッパを起こす。実 PATH を継承したうえで偽の実行ファイルの置き場を前置する。 */
function runWrapper(
    home: string,
    args: string[] = [],
    options: RunOptions = {},
): { status: number; stdout: string; stderr: string } {
    const platform = options.platform ?? LINUX_ARM64;
    const result = spawnSync("sh", [WRAPPER, ...args], {
        env: {
            ...process.env,
            HOME: home,
            PATH: `${fakeBinDir(platform, options.breakSort ?? false)}:${process.env.PATH ?? ""}`,
            ...(options.env ?? {}),
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

/** 標準エラー出力のうち、ラッパが出す固定の文の行だけを返す (可変のパスを含む行を除く)。 */
function fixedLines(stderr: string, home: string): string {
    return stderr
        .split("\n")
        .filter((line) => !line.includes(home))
        .join("\n");
}

/** 外した候補の行から、候補の絶対パスの集合を取り出す。 */
function listedCandidates(stderr: string): string[] {
    return stderr
        .split("\n")
        .filter(
            (line) =>
                line.includes(REASON_VERSION) || line.includes(REASON_BINARY),
        )
        .map((line) => line.slice(0, line.indexOf(": ")));
}

describe("scripts/codex — 実行環境の写像 (i3)", () => {
    it.each(ACCEPTED_PLATFORMS)(
        "A1 uname -s = $unameS / uname -m = $unameM なら $binRel の下の実行ファイルを起動する",
        (platform) => {
            const home = makeHome();
            const extDir = installExtension(
                home,
                ".vscode-server",
                extensionName("1.0.0", platform),
                platform,
            );

            const result = runWrapper(home, ["--version"], { platform });

            expect(result.status).toBe(0);
            expect(result.stdout).toContain(
                join(extDir, platform.binRel, "codex"),
            );
        },
    );

    it("A2 対応しない OS では、続行した場合に見つかる拡張があっても起動せずに落ちる", () => {
        const home = makeHome();
        const sunos: Platform = {
            unameS: "SunOS",
            unameM: "x86_64",
            binRel: "bin/linux-x86_64",
            extSuffix: "linux-x64",
        };
        // 対応しない OS を黙って linux として続行する実装が選ぶ組み合わせを置く
        installExtension(
            home,
            ".vscode-server",
            "openai.chatgpt-1.0.0-linux-x64",
            sunos,
        );

        const result = runWrapper(home, ["--version"], { platform: sunos });

        expect(result.status).toBe(1);
        expect(result.stdout).toBe("");
        expect(result.stderr).toContain("SunOS");
    });

    it("A3 対応しない CPU では、続行した場合に見つかる拡張があっても起動せずに落ちる", () => {
        const home = makeHome();
        const riscv: Platform = {
            unameS: "Linux",
            unameM: "riscv64",
            binRel: "bin/linux-aarch64",
            extSuffix: "linux-arm64",
        };
        // 対応しない CPU を黙って arm64 として続行する実装が選ぶ組み合わせを置く
        installExtension(
            home,
            ".vscode-server",
            "openai.chatgpt-1.0.0-linux-arm64",
            riscv,
        );

        const result = runWrapper(home, ["--version"], { platform: riscv });

        expect(result.status).toBe(1);
        expect(result.stdout).toBe("");
        expect(result.stderr).toContain("riscv64");
    });

    it("A4 ディレクトリ名の接尾辞ではなく uname が実行環境を決める", () => {
        const home = makeHome();
        const darwin: Platform = {
            unameS: "Darwin",
            unameM: "arm64",
            binRel: "bin/macos-aarch64",
            extSuffix: "darwin-arm64",
        };
        // 名前の接尾辞は linux-arm64 だが、uname は Darwin + arm64 を答える
        const extDir = installExtension(
            home,
            ".vscode-server",
            "openai.chatgpt-1.0.0-linux-arm64",
            darwin,
        );

        const result = runWrapper(home, ["--version"], { platform: darwin });

        expect(result.status).toBe(0);
        expect(result.stdout).toContain(join(extDir, darwin.binRel, "codex"));
    });
});

describe("scripts/codex — 候補の採否 (i1 / i2)", () => {
    it("B1 接尾辞の無い名前でも、同梱物が実在すれば起動する", () => {
        const home = makeHome();
        // この件だけ接尾辞を外す (2026-09-10 の事故の再現)
        installExtension(home, ".vscode-server", "openai.chatgpt-0.5.12");

        const result = runWrapper(home, ["--version"]);

        expect(result.status).toBe(0);
        expect(result.stdout).toContain(
            join("openai.chatgpt-0.5.12", LINUX_ARM64.binRel, "codex"),
        );
    });

    it("B2 候補が複数あれば辞書順ではなく版の新しい方を起動する", () => {
        const home = makeHome();
        installExtension(home, ".vscode-server", extensionName("0.5.9"));
        installExtension(home, ".vscode-server", extensionName("0.5.10"));

        const result = runWrapper(home, ["--version"]);

        expect(result.status).toBe(0);
        expect(result.stdout).toContain(extensionName("0.5.10"));
        expect(result.stdout).not.toContain(extensionName("0.5.9"));
    });

    it.each([
        {
            label: "(a) 古い方だけ接尾辞つき",
            oldName: extensionName("0.5.9"),
            newName: "openai.chatgpt-0.5.10",
        },
        {
            label: "(b) 新しい方だけ接尾辞つき",
            oldName: "openai.chatgpt-0.5.9",
            newName: extensionName("0.5.10"),
        },
    ])(
        "B3 $label でも版の新しい方を起動する (接尾辞の有無は比較を傾けない)",
        ({ oldName, newName }) => {
            const home = makeHome();
            installExtension(home, ".vscode-server", oldName);
            installExtension(home, ".vscode-server", newName);

            const result = runWrapper(home, ["--version"]);

            expect(result.status).toBe(0);
            expect(result.stdout).toContain(join(newName, LINUX_ARM64.binRel));
            expect(result.stdout).not.toContain(join(oldName, LINUX_ARM64.binRel));
        },
    );

    it.each([
        { label: "(a) 新しい版が ~/.vscode 側", newRoot: ".vscode" as const },
        {
            label: "(b) 新しい版が ~/.vscode-server 側",
            newRoot: ".vscode-server" as const,
        },
    ])("B4 2 つの置き場を跨いで版の新しい方を起動する — $label", ({ newRoot }) => {
        const home = makeHome();
        const oldRoot = newRoot === ".vscode" ? ".vscode-server" : ".vscode";
        installExtension(home, oldRoot, extensionName("1.0.0"));
        const newExtDir = installExtension(home, newRoot, extensionName("2.0.0"));

        const result = runWrapper(home, ["--version"]);

        expect(result.status).toBe(0);
        expect(result.stdout).toContain(
            join(newExtDir, LINUX_ARM64.binRel, "codex"),
        );
    });

    it("B5 同じ版が両方の置き場にあるときは ~/.vscode を起動する", () => {
        const home = makeHome();
        const preferred = installExtension(
            home,
            ".vscode",
            extensionName("1.0.0"),
        );
        installExtension(home, ".vscode-server", extensionName("1.0.0"));

        const result = runWrapper(home, ["--version"]);

        expect(result.status).toBe(0);
        expect(result.stdout).toContain(
            join(preferred, LINUX_ARM64.binRel, "codex"),
        );
    });

    it.each([
        { label: "不在", options: { omitBinary: true } },
        { label: "実行権の無い通常ファイル", options: { notExecutable: true } },
        {
            label: "codex という名前のディレクトリ",
            options: { binaryAsDirectory: true },
        },
    ])(
        "B6 最新版の実行ファイルが $label なら、飛ばして 1 つ前の版を起動する",
        ({ options }) => {
            const home = makeHome();
            installExtension(home, ".vscode-server", extensionName("0.5.9"));
            installExtension(
                home,
                ".vscode-server",
                extensionName("0.5.10"),
                LINUX_ARM64,
                options,
            );

            const result = runWrapper(home);

            expect(result.status).toBe(0);
            expect(result.stdout).toContain(extensionName("0.5.9"));
            expect(result.stdout).not.toContain(extensionName("0.5.10"));
        },
    );

    it("B7 版として読めない名前は、同梱物が実在しても候補にしない", () => {
        const home = makeHome();
        const extDir = installExtension(
            home,
            ".vscode-server",
            "openai.chatgpt-beta-linux-arm64",
        );

        const result = runWrapper(home);

        expect(result.status).toBe(1);
        expect(result.stdout).toBe("");
        expect(listedCandidates(result.stderr)).toEqual([extDir]);
        expect(fixedLines(result.stderr, home).toLowerCase()).not.toContain(
            "install",
        );
    });

    it("B8 版の部分が点で始まる名前も候補にしない", () => {
        const home = makeHome();
        const extDir = installExtension(
            home,
            ".vscode-server",
            "openai.chatgpt-.preview-linux-arm64",
        );

        const result = runWrapper(home);

        expect(result.status).toBe(1);
        expect(result.stdout).toBe("");
        expect(listedCandidates(result.stderr)).toEqual([extDir]);
        expect(fixedLines(result.stderr, home).toLowerCase()).not.toContain(
            "install",
        );
    });

    it("B9 同じ置き場で同じ版へ正規化される候補が並んだら、名前のバイト順で大きい方を起動する", () => {
        const home = makeHome();
        installExtension(
            home,
            ".vscode-server",
            "openai.chatgpt-0.5.12-Zulu-linux-arm64",
        );
        const expected = installExtension(
            home,
            ".vscode-server",
            "openai.chatgpt-0.5.12-alpha-linux-arm64",
        );

        const result = runWrapper(home, ["--version"], { env: { LC_ALL: "C" } });

        expect(result.status).toBe(0);
        expect(result.stdout).toContain(
            join(expected, LINUX_ARM64.binRel, "codex"),
        );
    });
});

describe("scripts/codex — 起動の契約 (i5)", () => {
    it("C1 引数が順序も中身も変えられずに届く", () => {
        const home = makeHome();
        installExtension(home, ".vscode-server", extensionName("1.0.0"));

        const result = runWrapper(home, ["exec", "a b", "--", "-x"]);

        expect(result.status).toBe(0);
        const args = result.stdout
            .split("\n")
            .filter((line) => line.startsWith("ARG="))
            .map((line) => line.slice("ARG=".length));
        expect(args).toEqual(["exec", "a b", "--", "-x"]);
    });

    it("C2 実行ファイルの終了コードをそのまま返す", () => {
        const home = makeHome();
        installExtension(
            home,
            ".vscode-server",
            extensionName("1.0.0"),
            LINUX_ARM64,
            { exitCode: 7 },
        );

        const result = runWrapper(home);

        expect(result.status).toBe(7);
    });

    it("C3 ホームの絶対パスに空白が含まれていても起動する", () => {
        const home = makeHome("codex wrapper space ");
        const extDir = installExtension(
            home,
            ".vscode-server",
            extensionName("1.0.0"),
        );

        const result = runWrapper(home, ["--version"]);

        expect(result.status).toBe(0);
        expect(result.stdout).toContain(
            join(extDir, LINUX_ARM64.binRel, "codex"),
        );
    });
});

describe("scripts/codex — 失敗理由の 2 状態 (i4)", () => {
    it("D1 状態 A — 探した置き場を並べ、導入の案内を出し、外した候補は列挙しない", () => {
        const home = makeHome();

        const result = runWrapper(home);

        expect(result.status).toBe(1);
        expect(result.stdout).toBe("");
        expect(result.stderr).toContain(
            join(home, ".vscode", "extensions", "openai.chatgpt-*"),
        );
        expect(result.stderr).toContain(
            join(home, ".vscode-server", "extensions", "openai.chatgpt-*"),
        );
        // 契約語は小文字の install である (大文字と小文字を区別する)
        expect(fixedLines(result.stderr, home)).toContain("install");
        // 外した候補の行は理由の 2 種類のいずれかを含む行として数える
        expect(listedCandidates(result.stderr)).toEqual([]);
    });

    it("D2 状態 B — 外した候補を過不足なく 1 件 1 行で出し、導入の案内は出さない", () => {
        const home = makeHome();
        const extDirs = [
            installExtension(
                home,
                ".vscode-server",
                extensionName("0.5.1"),
                LINUX_ARM64,
                { omitBinary: true },
            ),
            installExtension(
                home,
                ".vscode-server",
                extensionName("0.5.2"),
                LINUX_ARM64,
                { omitBinary: true },
            ),
        ];

        const result = runWrapper(home);

        expect(result.status).toBe(1);
        expect(result.stdout).toBe("");
        // 候補の行から取り出したパスの集合が、作った拡張の集合と完全に一致する
        expect(listedCandidates(result.stderr).slice().sort()).toEqual(
            extDirs.slice().sort(),
        );
        expect(
            result.stderr
                .split("\n")
                .filter((line) => line.includes(REASON_BINARY)),
        ).toHaveLength(2);
        // 要求した相対パスと uname の生の答えは、ラッパが出す固定の文の同じ 1 行に出る。
        // 候補の絶対パスを含む行を除いてから見ないと、外した候補の行の綴りで判定が通ってしまう。
        const requiredLine = fixedLines(result.stderr, home)
            .split("\n")
            .filter((line) => line.includes(LINUX_ARM64.binRel));
        expect(requiredLine).toHaveLength(1);
        // 綴り (bin/linux-aarch64) は uname -m の生の答え (aarch64) を部分文字列として含むので、
        // 綴りを取り除いた残りに対して生の答えを探す (そうしないと綴りだけで通ってしまう)。
        const withoutBinRel = requiredLine[0]
            .split(LINUX_ARM64.binRel)
            .join("");
        expect(withoutBinRel).toContain(LINUX_ARM64.unameS);
        expect(withoutBinRel).toContain(LINUX_ARM64.unameM);
        expect(fixedLines(result.stderr, home).toLowerCase()).not.toContain(
            "install",
        );
    });

    it("D3 版が読めない候補も状態 B の列挙に並ぶ", () => {
        const home = makeHome();
        const extDir = installExtension(
            home,
            ".vscode-server",
            "openai.chatgpt-beta-linux-arm64",
            LINUX_ARM64,
            { omitBinary: true },
        );

        const result = runWrapper(home);

        expect(result.status).toBe(1);
        expect(result.stdout).toBe("");
        expect(result.stderr).toContain(`${extDir}: ${REASON_VERSION}`);
        expect(fixedLines(result.stderr, home).toLowerCase()).not.toContain(
            "install",
        );
    });

    it("D4 ホームの絶対パスが install を含んでも状態 B が成立する", () => {
        const home = makeHome("codex-wrapper-install-");
        const extDir = installExtension(
            home,
            ".vscode-server",
            extensionName("0.5.1"),
            LINUX_ARM64,
            { omitBinary: true },
        );

        const result = runWrapper(home);

        expect(result.status).toBe(1);
        expect(result.stdout).toBe("");
        expect(listedCandidates(result.stderr)).toEqual([extDir]);
        expect(fixedLines(result.stderr, home).toLowerCase()).not.toContain(
            "install",
        );
    });
});

describe("scripts/codex — 版の比較に失敗したときの振る舞い (i1)", () => {
    // 版の比較と、同じ版どうしの名前の比較は実装では別の経路である。
    // 片方だけでは他方の失敗処理を通らないので 2 行で見る。
    it.each([
        {
            label: "(a) 版の違う候補 2 本",
            names: [extensionName("0.5.9"), extensionName("0.5.10")],
        },
        {
            label: "(b) 同じ置き場・同じ版・違う名前の候補 2 本",
            names: [
                "openai.chatgpt-0.5.12-Zulu-linux-arm64",
                "openai.chatgpt-0.5.12-alpha-linux-arm64",
            ],
        },
    ])(
        "E1 $label で sort が失敗したら、候補を 1 つも起動せずに終了コード 1 で落ちる",
        ({ names }) => {
            const home = makeHome();
            for (const name of names) {
                installExtension(home, ".vscode-server", name);
            }

            const result = runWrapper(home, [], { breakSort: true });

            expect(result.status).toBe(1);
            // 代理の実行ファイルへ到達していない (起動していれば STUB_PATH= の行が出る)
            expect(result.stdout).toBe("");
            expect(result.stderr).not.toBe("");
        },
    );
});
