# QASAS Kobe Ver 2.0 経時解析方法仕様

## 1. 目的

Ver 2.0は、Ver 1.0の単独検体解析を変更せず、複数のレパトア検体を任意の数値Dayに配置して経時表示する機能を追加した版です。各時点の照合結果は独立に計算し、その後で表示用の系列へまとめます。

時間軸を追加しても、IGHV・IGHJ・CDR3の正規化、候補選択、Levenshtein距離、LV区分、頻度分母は単独解析と同じです。3方式の詳細は [MATCHING_METHODS.md](MATCHING_METHODS.md) を参照してください。

## 2. 入力

経時解析全体で固定する入力:

- 系列名（任意）
- 抗原結合性データベースCSV 1ファイル
- 照合方式 1種類: `legacy`、`kobe`、`cdr3-only`

各時点で入力する情報:

- `Day`: 有限な数値
- `Label`: 任意の表示名
- `Sample`: CPM CSV/TSVまたはRG Excel
- `Format`: `AUTO`、`CPM`、`RG`

Dayは負数、0、正数、小数を許可します。例: `-14`、`-0.5`、`0`、`3`、`14.5`。`Day14`のような文字列、空欄、NaN、無限大は許可しません。Labelには`Pre`や`D14`など自由な文字列を記録できます。

同じ数値Dayを2件以上登録すると解析を停止します。Ver 2.0は反復検体を暗黙に平均・合算しません。反復の扱いを将来追加する場合は、平均対象、重み、分母を別仕様として明示します。

## 3. 計算手順

実装は `qasas/timecourse.py` の `analyse_timecourse()` です。

```text
1. 全Dayを有限な数値として検証する
2. 同一Dayがないことを確認する
3. Dayの数値昇順に並べる
4. 選択した照合方式で共通DBを1回読み込む
5. 各時点について独立に以下を行う
   a. その検体をCPM/RGローダーで読み込む
   b. Ver 1.0と同じanalyse()を実行する
   c. 個別LV0/LV1/LV2と累積≤LV0/≤LV1/≤LV2を保存する
6. Dayを実数のx座標としてグラフ化する
```

補間、平滑化、欠測値補完、時点間のRead合算は行いません。Day間隔が`0, 1, 14`なら、x軸上の間隔も1対13です。

## 4. 集計式

検体クローン`c`について、選択した方式で許可されるDB候補とのCDR3アミノ酸Levenshtein距離の最小値を`d(c)`とします。

個別距離`k`（LVk）:

```text
UniqueClones(k) = count of c where d(c) = k
TotalReads(k)   = sum Reads(c) where d(c) = k
Frequency(k)    = sum Frequency(c) where d(c) = k
```

累積距離`k`（≤LVk）:

```text
UniqueClones(≤k) = count of c where d(c) ≤ k
TotalReads(≤k)   = sum Reads(c) where d(c) ≤ k
Frequency(≤k)    = sum Frequency(c) where d(c) ≤ k
```

頻度は各検体の分母から独立に計算します。複数時点のReadや分母をプールしません。RGの分母規則は照合方式に依存し、`legacy`では列挙in-frame Read合計、`kobe`と`cdr3-only`では利用可能な`In-frame reads`を優先します。

## 5. GUI表示

上部タブ:

- `単独検体解析（Ver 1.0画面）`: 従来の入力、サマリー、一致クローン、1×3棒グラフを保持
- `経時・複数検体解析（Ver 2.0）`: Day付き複数入力と経時結果

経時グラフの既定値は論文形式の2×3です。

- 列: ≤LV0、≤LV1、≤LV2
- 上段: ユニーククローン数
- 下段: 頻度（%）

`3指標（3×3）`では中央段に総リード数を追加します。`累積`と`個別`は切替可能です。`選択検体の単独Fig`では、経時系列内の1時点を選び、Ver 1.0と同じ個別LV0/LV1/LV2の1×3棒グラフを表示します。

## 6. Excel出力

`export_timecourse_xlsx()`は次のシートを保存します。

| シート | 内容 |
|---|---|
| `Time Course Summary` | Day順の横持ち集計、累積/個別3指標、Excel折れ線グラフ |
| `Long Summary` | 1行=1時点×1集計種別×1距離の縦持ち表 |
| `Sample QC` | 時点ごとの入力様式、行数、クローン数、Read分母、メタデータ |
| `Matched Clones` | Day・検体情報付き一致クローンとDB注釈 |
| `Method` | アプリ版、経時モジュール版、照合アルゴリズム版、固定規則 |

アプリ版は`QASAS Kobe Ver 2.0`、経時モジュール識別子は`QASAS-Kobe-timecourse-2.0`です。照合アルゴリズム自体はVer 1.0から変更していないため、識別子`QASAS-Kobe-three-mode-1.0`を保持します。

## 7. CLIによる再実行

UTF-8 CSVマニフェストを作成します。相対Sampleパスはマニフェストの保存場所を基準に解決します。

```csv
Day,Label,Sample,Format
-7,Pre,inputs/sample_pre.xlsx,RG
0,Baseline,inputs/sample_day0.xlsx,RG
14.5,D14.5,inputs/sample_day14_5.csv,CPM
```

実行例:

```powershell
python qasas_timecourse_cli.py `
  --manifest timecourse_manifest.csv `
  --database "QASAS データベース CoV-AbDab\CoV-AbDab_080224.csv" `
  --mode kobe `
  --series-name "Patient A" `
  --output "QASAS 結果\Patient_A_timecourse.xlsx"
```

## 8. 再現性上の注意

結果を比較するときは、Gitコミット、照合方式、検体/DBのSHA-256、入力様式、Day、Labelを保存してください。異なる照合方式の結果を同一手法として混合しないでください。DBを交換・追加した場合は、同じ検体でも一致数が変わることが正しい挙動です。
