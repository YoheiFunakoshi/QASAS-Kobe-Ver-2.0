# QASAS Kobe Ver 2.0

QASAS（Quantification of Antigen-Specific Antibody Sequences）は、検体のBCRレパトア解析結果と、抗原結合性が既知のBCR／抗体配列データベースを照合するWindowsアプリです。

IGHV・IGHJ・CDR3アミノ酸配列を用いて、CDR3の完全一致（LV0）、Levenshtein距離1（LV1）、距離2（LV2）を区別し、一致したユニーククローン数、総リード数、頻度を表示・保存します。特定の抗原に固定しておらず、必要列を持つデータベースCSVへ交換・追加できます。

Ver 2.0は、Ver 1.0の単独検体画面と計算エンジンを保持したまま、Day付きの複数検体を経時表示する機能を追加しています。

## 主な機能

### 単独検体解析（Ver 1.0画面）

- RG社形式（Excel）／CPM社形式（CSV/TSV）を明示する選択ボタンと、ファイル選択時の自動判定
- 将来の入力形式追加用に、無効状態の「汎用形式（今後対応）」ボタンを配置
- CoV-AbDab／汎用データベースを明示する選択ボタンを配置
- 旧QASAS／Kobe Ver 1.0／CDR3のみの3照合方式
- 個別LV0・LV1・LV2、累積≤LV0・≤LV1・≤LV2
- ユニーククローン、総リード、頻度の1×3 Fig
- 一致クローンとDB注釈の一覧
- 解析条件・QCを含むExcel保存

### 経時・複数検体解析（Ver 2.0）

- 2件以上のCPM/RG検体を1系列に登録
- Dayは自由入力: 負数、0、正数、小数に対応
- 1つの共通DBと1つの照合方式で各検体を独立解析
- Dayの数値昇順・実間隔で折れ線表示
- 論文形式2×3 Fig: 上段=ユニーククローン、下段=頻度、列=LV0/≤LV1/≤LV2
- 3×3表示で総リードを追加可能
- 累積と個別距離を切替可能
- 経時系列から1時点を選び、従来の単独1×3 Figを表示
- 経時Figをダブルクリック、または「Figを大きく表示」から独立した可変サイズウィンドウで確認可能
- 画像保存は埋め込み画面の大きさに依存せず、余白を確保した高解像度レイアウトから出力
- 経時ExcelとPNG/PDF Figを保存

同一Dayは自動平均しません。重複Dayを検出すると停止し、意図しないプールや平均を防ぎます。頻度は各検体の分母で独立に計算されます。

## 照合方式

| 方式 | CLI | V/J条件 | 主な目的 |
|---|---|---|---|
| 旧QASAS方式 | `legacy` | 入力V/J文字列と旧互換DBキーの完全一致。アレル表記差も不一致 | 旧QASAS2の照合中核を再現 |
| Kobe Ver 1.0方式 | `kobe` | V/J候補を分割・正規化し、いずれかのV/J組合せが一致 | 複数候補やアレル表記差を許容 |
| CDR3のみ方式 | `cdr3-only` | V/Jを候補制限に使用しない | V/Jコール差に依存しない感度解析 |

方式ごとにクローン定義と候補選択が異なります。異なる方式の結果を同じ解析法として合算しないでください。詳細、例、旧QASAS2コードとの対応は [照合方法仕様](docs/MATCHING_METHODS.md) に固定しています。

> **CPM様式と旧QASAS方式に関する重要な注意**
>
> 現時点で本プロジェクトに提供されているCPM仕様情報では、V/Jのアレルまで判定せず、`*01`が便宜的に付与される形式とされています。この`*01`を生物学的に確定したアレルとは扱いません。旧QASAS方式はV/J文字列全体を完全一致させ、片方だけにアレル表記がある場合も、不明なアレルとして無視せず不一致とします。そのため、CPM様式には旧QASAS方式を原則使用しません。
>
> CPM様式の主解析にはKobe Ver 1.0方式を使用し、必要に応じてCDR3のみ方式を感度解析として併記してください。CPM様式を旧QASAS方式で解析して0になった場合、その0を「抗原特異的クローンなし」という生物学的陰性として解釈してはいけません。V/J表記が旧方式と非互換で、CDR3距離が評価される前に候補が0になった可能性を確認してください。
>
> 旧QASAS方式の実装は旧結果の再現性を守るため変更しません。アレルを除去して遺伝子名単位で照合する処理はKobe Ver 1.0方式です。

## 入力様式

単独検体画面と経時・複数検体画面のどちらにも、`RG社形式（Excel）`、`CPM社形式（CSV/TSV）`、`汎用形式（今後対応）`の選択ボタンがあります。検体ファイルを参照するとRG/CPMを自動判定して該当ボタンを選択し、その後に手動で切り替えることもできます。経時解析では、各時点を追加する際に確定した入力形式を一覧と処理ログへ記録します。

`汎用形式（今後対応）`は将来拡張のための表示のみで、現時点では選択できず、解析処理もありません。未実装の汎用形式が誤って既存ローダーへ渡らない設計です。将来形式を追加するときは、`qasas/input_formats.py`の選択肢と対応ローダーを追加します。

将来は、各社・各解析ソフトの異なるレパトア形式からVコール、Jコール、CDR3 AA、リード数／カウント数を抽出する別の変換アプリを作り、標準化した汎用Excelをこのボタンから入力する計画です。QASAS本体が未知の生ファイルを直接推測読込する設計にはしません。必須項目、COUNT単位、アレル情報、検証、形式バージョン、ボタン有効化条件は[汎用レパトアExcelと変換アプリの将来計画](docs/GENERIC_INPUT_FORMAT_PLAN.md)に記録しています。

データベース側にも`CoV-AbDab（CSV）`と`汎用データベース（今後対応）`の選択ボタンがあります。現在はCoV-AbDabだけを使用でき、汎用データベースは将来用の無効ボタンです。将来は多様な抗体・BCR配列データベースからVコール、Jコール、CDR3 AAと必要な注釈を整理する別アプリを作り、標準化した汎用データベースExcelを入力します。詳細は[汎用抗体データベースExcelと整理アプリの将来計画](docs/GENERIC_DATABASE_FORMAT_PLAN.md)に記録しています。

ファイル名を直接入力した場合も、解析開始時または時点追加時に自動判定を行い、選択ボタンへ反映します。

### CPM様式

CSV/TSVから次の列名候補を認識します。

| 内容 | 列名候補 |
|---|---|
| IGHV | `Vseg`, `V gene`, `IGHV` |
| IGHJ | `Jseg`, `J gene`, `IGHJ` |
| CDR3 AA | `CDR3`, `CDR3 AA`, `junction_aa` |
| Read数 | `Counts`, `Count`, `Reads`, `Read count`, `DUPCOUNT` |

### RG様式

Excel（`.xlsx`, `.xlsm`）の`Back_data`シートを全件読み込みます。

| Excel列 | 内容 |
|---|---|
| G | IGHV |
| K | IGHJ |
| O | CDR3 AA |
| P | frame。`in-frame`のみ採用 |
| Q | Reads |

古いRG Excelのワークシート範囲情報が途中で切れていても実セルを通常モードで走査します。列挙Readがレポート記載`In-frame reads`の95%未満なら、途中読み込みの疑いとして停止します。

### 抗体データベース

CSV/TSVに少なくともIGHV、IGHJ、CDR3 AA列が必要です。

| 内容 | 列名候補 |
|---|---|
| IGHV | `Heavy V Gene`, `IGHV`, `V gene`, `Vseg` |
| IGHJ | `Heavy J Gene`, `IGHJ`, `J gene`, `Jseg` |
| CDR3 AA | `CDRH3`, `CDR3`, `CDR3 AA`, `junction_aa` |

`Name`、`Binds to`、`Protein + Epitope`など他の列は注釈として保持・出力します。

データベースには検体レパトアのようなRead数／カウント数は必要ありません。V、J、CDR3 AAの3項目で照合キーを作れます。抗体名、対象抗原、出典などは照合の最小条件ではありませんが、一致配列の意味と由来を確認するため保持を推奨します。

## インストールと起動

WindowsとPython 3.11以降を推奨します。

1. 初回のみ`QASAS_セットアップ.cmd`をダブルクリックします。
2. `QASASを開く.cmd`をダブルクリックします。
3. 上部タブで`単独検体解析`または`経時・複数検体解析`を選びます。

手動実行:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe QASAS_app.pyw
```

## 経時解析の操作

1. `経時・複数検体解析（Ver 2.0）`タブを開きます。
2. 系列名、共通DB、照合方式を設定します。
3. Day、任意の表示名、入力様式、検体ファイルを設定し、`時点を追加`を押します。
4. 2件以上追加します。行を選ぶと更新・削除できます。
5. `経時QASAS解析を実行`を押します。
6. 経時グラフ、選択検体の単独Fig、経時サマリー、ログを確認します。
7. 必要に応じてExcelとPNG/PDFを保存します。

Dayの厳密な扱い、計算式、Excel構造、CLIマニフェストは [経時解析方法仕様](docs/TIMECOURSE_METHOD.md) を参照してください。

## コマンドライン再実行

単独検体:

```powershell
python qasas_cli.py `
  --sample "sample.xlsx" `
  --database "database.csv" `
  --format RG `
  --mode kobe `
  --output "QASAS 結果\sample_kobe.xlsx"
```

経時解析（マニフェスト方式）:

```powershell
python qasas_timecourse_cli.py `
  --manifest "timecourse_manifest.csv" `
  --database "database.csv" `
  --mode kobe `
  --series-name "Patient A" `
  --output "QASAS 結果\Patient_A_timecourse.xlsx"
```

## 出力

単独Excel:

- `Summary`
- `Method`
- `Input QC`
- `Matched Clones`

経時Excel:

- `Time Course Summary`
- `Long Summary`
- `Sample QC`
- `Matched Clones`
- `Method`

Excelの`Method`に、アプリ版、照合アルゴリズム版、照合方式、経時解析規則を記録します。

## 再現性

- アプリ版: `QASAS Kobe Ver 2.0`
- 経時モジュール: `QASAS-Kobe-timecourse-2.0`
- 照合アルゴリズム: `QASAS-Kobe-three-mode-1.0`

照合アルゴリズム識別子を1.0のまま保持するのは、Ver 2.0で単独検体の照合ロジックを変更していないためです。結果再現時はGitコミット、照合方式、検体/DB SHA-256、入力様式、Dayを固定してください。詳細は [再現手順](docs/REPRODUCIBILITY.md) を参照してください。

## 検証

```powershell
python -m compileall -q qasas qasas_cli.py qasas_timecourse_cli.py QASAS_app.pyw
python -m unittest discover -v
```

Ver 2.0では既存16テストに経時4テストを追加しています。負数・0・正数・小数Day、数値ソート、重複Day停止、各時点と単独解析の同一性、経時Excel構造を検証します。実データKKF103hG・KKF141hGでも経時内の各時点が単独解析と完全一致することを確認しています。基準値は [検証結果](docs/VALIDATION_RESULTS.md) に記録しています。

## データ保護

アプリは入力検体とDBを読み取り専用で扱い、内容を変更しません。検体、DB、論文、生成結果は`.gitignore`の対象です。公開GitHubへ研究データや解析結果を登録しないでください。
