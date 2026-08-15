# QASAS Kobe Ver 2.0 再現手順

Ver 2.0の経時解析固有の入力規則、計算式、CLIマニフェストは [TIMECOURSE_METHOD.md](TIMECOURSE_METHOD.md) も参照してください。単独検体の照合アルゴリズムはVer 1.0から変更していません。

## 1. 再現に必要な固定情報

結果を再現するには、少なくとも次を固定します。

1. QASAS Kobeリポジトリの40桁Gitコミット。
2. アルゴリズム識別子 `QASAS-Kobe-three-mode-1.0`。
3. 照合方式 `legacy`、`kobe`、`cdr3-only` のいずれか。
4. 検体ファイルのSHA-256、入力様式、ファイル名。
5. DBファイルのSHA-256、列名、取得日・版。
6. Python、`openpyxl`、`matplotlib`、OSの版。
7. 出力Excelの `Method` と `Input QC`。

ファイル名が同じでも内容が同じとは限りません。必ずSHA-256で同一性を確認します。

現在の通常解析・経時解析Excelは、保存時に検体とDBのSHA-256、ファイルサイズ、更新時刻を自動計算して `Input QC` または `Sample QC` と `Method` に記録します。さらにGitコミット、作業ツリー状態、QASASソース全体のSHA-256、Python・主要ライブラリ・OSの版も `Method` に記録します。入力データ本体がExcelやGitHubへ複製・送信されることはありません。

`Git working tree` が `modified` の場合は、同じコミットでも未コミット変更を含む状態です。その場合は `Application source SHA-256` も一致することを確認してください。正式な再現用解析では、可能な限り `clean` の状態を使用します。

## 2. ソースコードの固定

解析に使用したリポジトリで次を実行し、結果と一緒に保存します。

```powershell
git rev-parse HEAD
git status --short
git remote -v
```

再計算時は同じコミットをcheckoutします。

```powershell
git fetch origin
git checkout <保存した40桁コミット>
```

作業ツリーに未保存変更がある状態では、同じコミット名でも実際のコードが異なるため解析しないでください。`git status --short` が空であることを確認します。

## 3. Python環境の固定

推奨はPython 3.11以降です。新しい仮想環境を作り、リポジトリの `requirements.txt` を使用します。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip freeze | Out-File -Encoding utf8 environment-pip-freeze.txt
```

OSとロケールも保存します。

```powershell
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber |
  Format-List | Out-File -Encoding utf8 environment-windows.txt
Get-Culture | Format-List | Out-File -Append -Encoding utf8 environment-windows.txt
```

## 4. 入力ハッシュ

```powershell
Get-FileHash -Algorithm SHA256 "<検体ファイル>"
Get-FileHash -Algorithm SHA256 "<DBファイル>"
```

ハッシュ、ファイルサイズ、更新時刻も一覧へ保存できます。

```powershell
Get-Item "<検体ファイル>", "<DBファイル>" |
  Select-Object FullName, Length, LastWriteTime |
  Export-Csv -NoTypeInformation -Encoding utf8 input_manifest.csv
```

## 5. 3方式の固定実行

GUIでも同じエンジンを使いますが、自動再現にはCLIを推奨します。

```powershell
$samplePath = "<検体ファイル>"
$databasePath = "<DBファイル>"

python qasas_cli.py --sample $samplePath --database $databasePath `
  --format RG --mode legacy --output results\sample_legacy.xlsx
python qasas_cli.py --sample $samplePath --database $databasePath `
  --format RG --mode kobe --output results\sample_kobe.xlsx
python qasas_cli.py --sample $samplePath --database $databasePath `
  --format RG --mode cdr3-only --output results\sample_cdr3-only.xlsx
```

CPMの場合は `--format CPM`、自動判定する場合は `--format AUTO` を使います。

ただし、現時点で本プロジェクトに提供されているCPM仕様情報では、V/Jの`*01`がアレル判定結果ではなく便宜的に付与される形式とされています。CPMの再現解析では原則として`--mode kobe`を主解析、`--mode cdr3-only`を感度解析に使用し、`--mode legacy`は使用しません。旧QASAS方式の0は、V/J完全一致候補が作れずCDR3距離が未評価の可能性があるため、生物学的陰性として報告しないでください。

旧QASAS方式を使用する場合は、検体とDBのV/J表記規則が同じであること、アレル情報が実測・推定・便宜的付与のいずれかを記録してください。片側のアレル欠損は旧方式ではワイルドカードにならず不一致です。

3方式を一度に実行し、ハッシュ付きJSONを保存する標準手順は次です。

```powershell
python scripts\validate_three_modes.py `
  --sample $samplePath `
  --database $databasePath `
  --format RG `
  --output-dir results\three-mode-validation
```

出力先には方式別Excel 3ファイルと `validation_summary.json` が作成されます。JSONには入力・DBのSHA-256と、個別／累積LVのクローン数・Read・頻度が入ります。

## 6. 解析前の受入試験

```powershell
python -m compileall -q qasas qasas_cli.py QASAS_app.pyw
python -m unittest discover -v
```

すべて `OK` で終了することを確認します。現在の試験は次を含みます。

- LV0、LV1、LV2の個別・累積区分。
- 旧QASASのV/J文字列完全一致。
- 旧QASASの距離0～2全DB候補保持と最小距離区分。
- Kobeの複数V/J候補一致。
- CDR3のみ方式のV/J非依存照合とCDR3単位集約。
- CDR3削除索引と総当たりLevenshtein判定の一致。
- CPM列読込み、RG `Back_data` 全件読込み、out-of-frame除外。
- CoV-AbDab型DBのHuman／Bind-or-Neut旧フィルタ。
- Excel `Method`、`Input QC`、`Matched Clones` 出力。

## 7. 実データの段階的照合

最終グラフだけでなく、次の順に比較すると差の原因を特定できます。

1. 検体SHA-256とDB SHA-256。
2. `Input QC` の検体source／accepted／skipped行数。
3. 検体の正規化ユニーククローン数、listed reads、frequency denominator。
4. DB source／usable／skipped行数、正規化一意キー数。
5. `Summary` の個別LV0、LV1、LV2。
6. `Summary` の累積≤LV0、≤LV1、≤LV2。
7. `Matched Clones` のCDR3、Read、最小距離、保持DB候補数。
8. DB注釈列。

1～4が違えば入力・正規化・分母の差、5以降だけが違えば候補選択・距離・DB内容の差を疑います。

## 8. 保存すべき解析一式

推奨フォルダ構成は次のとおりです。

```text
analysis-YYYYMMDD/
  source_commit.txt
  environment-pip-freeze.txt
  environment-windows.txt
  input_manifest.csv
  input_sha256.txt
  validation_summary.json
  sample_legacy.xlsx
  sample_kobe.xlsx
  sample_cdr3-only.xlsx
  notes.txt
```

検体データやDBをGitHubへ登録してはいけません。施設の規則に従った保護領域へ保存します。

## 9. 結果報告に必要な記載

論文、報告書、図注には、最低限次を明示します。

- 「QASAS Kobe Ver 2.0」およびGitコミット。経時解析では経時モジュール識別子も記載。
- アルゴリズム識別子。
- 照合方式。
- 検体入力様式（CPM／RG）。
- DB名、版／日付、SHA-256。
- CDR3距離がLevenshtein距離0～2であること。
- 個別値か累積値か。
- ユニーククローンの定義。
- 頻度分母。

例:

> BCR repertoires were compared with the specified antibody-sequence database using QASAS Kobe Ver 2.0 (`QASAS-Kobe-three-mode-1.0`; longitudinal module `QASAS-Kobe-timecourse-2.0`; Kobe mode; Git commit `<hash>`). Each time point was analysed independently. Candidate-aware allele-free IGHV/IGHJ calls and CDR3 amino-acid Levenshtein distances of 0–2 were used. Exact distance classes and cumulative values were reported separately.

## 10. 旧QASAS2再現の注意

旧QASAS方式は、QASAS2 `function2.R` の `readreport2()`、`createdb2.base()`、`createdb2()`、`findcov2()` に関係する照合中核を対象とします。QASAS2のRパッケージ環境、注釈別 `sumcov2()`、時系列処理、Virus／Strain／Variant分類、旧グラフ外観まで含む完全なR実行環境の再現ではありません。

旧QASAS2の完全なR処理を再現する場合は、別途作成した「旧QASAS2照合・集計方法 再現手順書」と固定コミット `b1987209a7b2fb5bc0a55360654b79d01384dccb` を使用してください。

