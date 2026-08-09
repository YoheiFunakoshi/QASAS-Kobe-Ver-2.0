# QASAS Kobe Ver 1.0 照合方式固定仕様

## 1. 文書の目的

本書は、QASAS Kobe Ver 1.0の3方式で「どの行を読み、何を1クローンとし、どのDB配列を比較し、どのようにLV0／LV1／LV2へ分類するか」を固定します。同じ入力ファイル、同じDB、同じGitコミット、同じ方式を使用すれば、別の解析者が同じ集計値を再計算できることを目的とします。

アルゴリズム識別子は `QASAS-Kobe-three-mode-1.0` です。

旧QASAS方式の一次資料は、研究グループのprivateリポジトリ `takajim/QASAS2` の次の固定版です。

- リポジトリ全体: `main` @ `b1987209a7b2fb5bc0a55360654b79d01384dccb`
- 照合主要コード: `function2.R` @ `00f2061132a7dc32902199aebd050bc887dd4265`
- 参照日: 2026年8月9日

旧リポジトリは仕様確認のために閲覧しただけで、変更していません。

## 2. 共通の解析対象

検体側では正のReadを持つin-frame配列だけを扱います。DB側ではIGHV、IGHJ、CDR3アミノ酸配列と任意の注釈列を読みます。解析の大枠は次のとおりです。

1. 入力方式に従って検体行を読み込む。
2. 選択方式のクローンキーで検体行を統合し、Readを合算する。
3. 選択方式のDBキーでDB行を統合し、注釈をまとめる。
4. 選択方式の規則でDB候補を選ぶ。
5. 検体CDR3とDB CDR3のLevenshtein距離を計算する。
6. 距離0～2だけを一致とし、検体クローンを候補中の最小距離へ分類する。
7. 個別LV0／LV1／LV2と累積≤LV0／≤LV1／≤LV2を集計する。

## 3. 検体読込み

### 3.1 CPM様式

CPM CSV／TSVからV、J、CDR3、Read数を読みます。Read数が0以下、必須配列が空、または方式上必要なV/Jが空の行を除外します。

- 旧QASAS／Kobe Ver 1.0: V、J、CDR3が必要。
- CDR3のみ: CDR3だけが必須。V/Jは表示情報として可能な範囲で保持。

頻度分母は採用行をクローン統合した後のRead合計です。

### 3.2 RG様式

RG Excelの `Back_data` を列G～Qの実セル範囲で読みます。G=IGHV、K=IGHJ、O=CDR3、P=Frame、Q=Readです。Frameを空白・記号を除いて小文字化した値が `inframe` の行だけを採用し、正のReadを要求します。

旧QASAS2の `readreport2()` は固定範囲 `G1:Q99999` でした。本アプリは、Excelの誤ったキャッシュ範囲による切断を防ぐため、`Back_data` の実セルを全件読みます。この差は読込みの欠落を防ぐ安全修正であり、同じ有効行集合に対する照合規則は旧方式に合わせています。

### 3.3 検体クローン統合

| 方式 | 統合キー | Read |
|---|---|---|
| 旧QASAS | 前後空白を除いた生IGHV × 生IGHJ × 生CDR3 | 同一キー内で合算 |
| Kobe Ver 1.0 | 正規化V候補タプル × 正規化J候補タプル × 正規化CDR3 | 同一キー内で合算 |
| CDR3のみ | 正規化CDR3 | V/Jに関係なく同一CDR3を合算 |

候補タプルは順序を保持します。したがって、同じ候補集合でも入力順序が異なる文字列はKobe方式で別の検体キーになり得ます。DB候補探索時は各候補を個別に使います。

## 4. 正規化規則

### 4.1 `clean_text`

前後空白を除きます。空文字、および大文字化した値が `-`、`--`、`N/A`、`NA`、`NAN`、`NONE`、`NULL`、`ND`、`UNKNOWN`、`UNASSIGNED` のいずれかなら空値とします。

### 4.2 Kobe Ver 1.0のIGHV／IGHJ

次の順に処理します。

1. 丸括弧部分を除く。
2. 単語 `OR`、`AND` を候補区切りへ変換する。
3. `//`、`,`、`;`、`|`、`/` で候補を分割する。
4. 大文字化し、空白を除く。
5. IGHJの誤記 `IHGJ...` を `IGHJ...` へ直す。
6. 末尾のアレル指定 `*...` を除く。
7. 末尾の `.`、`:` を除く。
8. 文字列中の期待接頭辞 `IGHV...` または `IGHJ...` を抽出する。
9. 入力順を保ったまま重複候補を除く。

例: `IGHV3-53*01 // IGHV3-66*02 (Human)` は `IGHV3-53`、`IGHV3-66` になります。

旧QASAS方式はこの正規化を行いません。CDR3のみ方式では同じ処理結果を表示用に保持しますが、候補制限には使いません。

### 4.3 Kobe Ver 1.0／CDR3のみのCDR3

1. 前後空白を除く。
2. 大文字化する。
3. `A`～`Z` と `*` 以外を除く。
4. 長さ3以上で先頭がC、末尾がWなら、両方を1文字ずつ除いて内部配列を比較する。

DBのCDR3は、非空行の80%以上がC…W形式ならDB全体を「保存端あり」と判定して同じ端除去を行います。80%未満ならDB側の端除去を行いません。この判定数はExcelの `Input QC` に記録します。

### 4.4 旧QASASのCDR3

- 検体CDR3: 前後空白以外は変更しない。
- DB CDRH3: 生文字列の先頭に `C`、末尾に `W` を無条件で1文字ずつ付ける。

これは旧 `createdb2.base()` の挙動です。DBが既にC…Wを含む場合でも `CC…WW` となるため、旧方式用DBはC/Wを含まないCDRH3を前提とします。

## 5. DB前処理

### 5.1 旧QASAS方式

CoV-AbDab型のDBに対し、旧 `createdb2.base()` の照合に関係する処理を再現します。

1. DB内のVまたはJに `Human` を含む行が1行でもあればHumanフィルタを有効にする。
2. Humanフィルタ有効時は、IGHVとIGHJの両方に `Human` を含む行だけを残す。
3. IGHV／IGHJ末尾の正確な文字列 ` (Human)` だけを除く。
4. `Binds to`／非結合、`Neutralising Vs`／非中和列が存在する場合、セミコロンで注釈を分け、`(weak)` と空白を除く。
5. `Bind - notBind` または `Neut - notNeut` が空でない行だけを残す。
6. DB CDRH3へC/Wを無条件付加する。
7. IGHV × IGHJ × CDR3dbで一意化し、元注釈を統合する。

旧QASAS2の注釈別 `number` 集計、Virus／Strain／Variant分類、複数時点の図示は本アプリの現バージョンには含みません。旧方式が再現する範囲は、検体クローン化、DB行フィルタ、V/J候補制限、CDR3距離、最小距離区分、および距離0～2候補保持です。

### 5.2 Kobe Ver 1.0方式

各DB行の正規化V候補と正規化J候補の直積を作り、`V候補 × J候補 × 正規化CDR3` で一意化します。同一キーの元DB注釈は重複を除いて統合します。

### 5.3 CDR3のみ方式

DBキーは正規化CDR3だけです。同じCDR3の全DB行の注釈を統合します。元のV/Jは `DB IGHV source`、`DB IGHJ source` 注釈として保持します。

## 6. 候補選択と距離計算

### 6.1 Levenshtein距離

置換、挿入、削除の各コストを1とする通常のLevenshtein距離です。最大距離は2です。長さ差が2を超える候補は一致しません。動的計画法は距離2を超えた時点で打ち切りますが、LV0～LV2の値は完全計算と同じです。

### 6.2 旧QASAS方式

検体の生IGHV文字列と生IGHJ文字列が、前処理後DBのIGHV／IGHJに両方とも完全一致する候補だけを比較します。カンマ区切りや `//` の複合候補を分けません。アレルも除きません。

この挙動は、アレル番号を別フィールドとして比較する専用判定ではありません。旧 `readreport2()` は検体のIGHV・IGHJを加工せず、旧 `createdb2.base()` はDB末尾の正確な文字列 ` (Human)` だけを除去し、旧 `findcov2()` が `by = c("IGHV", "IGHJ")` で文字列全体を結合します。そのため、文字列にアレルが含まれていれば結果としてアレル一致が必須になります。IGHJも同じです。

| 検体IGHV | 前処理後DB IGHV | 判定 | 理由 |
|---|---|---|---|
| `IGHV3-53*01` | `IGHV3-53*01` | 一致 | 文字列全体が同じ |
| `IGHV3-53*01` | `IGHV3-53*02` | 不一致 | アレルが異なる |
| `IGHV3-53` | `IGHV3-53*01` | 不一致 | 一方だけにアレル表記がある |
| `IGHV3-53` | `IGHV3-53` | 一致 | 文字列全体が同じ |

したがって旧QASAS方式を再現する場合、アレルを除去して遺伝子名だけで照合してはいけません。遺伝子名単位へ正規化して照合したい場合はKobe Ver 1.0方式を使用します。

### 6.3 Kobe Ver 1.0方式

検体V候補のいずれかとDB V候補、検体J候補のいずれかとDB J候補が両方一致する場合に候補とします。候補CDR3長は検体長±2に限定します。複数のV/J組合せから同じDBキーへ到達しても、1回だけ距離を計算します。

### 6.4 CDR3のみ方式

V/Jを使いません。全DBとの直積を避けるため、DB CDR3から0～2文字を削除して得られる全「削除シグネチャ」を索引化します。検体CDR3についても同じシグネチャを作り、共通シグネチャを持つDBだけを候補にします。

距離2以下の2文字列は、半径2の削除シグネチャ集合に少なくとも1つ共通要素を持つため、この索引は真のLV0～LV2候補を除外しません。索引は余分な候補を含み得るので、最終判定は必ず通常のLevenshtein距離で再計算します。索引は速度だけを変え、結果を近似しません。

## 7. 最小距離とDB候補保持

検体クローン `s` と候補DB集合 `D(s)` に対し、クローン区分は次式です。

```text
d_min(s) = min { LV(CDR3_sample(s), CDR3_database(d)) | d in D(s) }
```

`d_min` が0、1、2なら一致、3以上または候補なしなら不一致です。

| 方式 | Excelへ保持するDB候補 | クローン区分 |
|---|---|---|
| 旧QASAS | 距離0～2の候補をすべて保持 | その全候補中の最小距離 |
| Kobe Ver 1.0 | 最小距離と同距離の候補だけ保持 | 最小距離 |
| CDR3のみ | 最小距離と同距離の候補だけ保持 | 最小距離 |

旧方式で、同じ検体クローンに距離0と距離2のDB候補があれば、両方の注釈を保持し、クローン自体はLV0へ1回だけ計上します。これは旧 `findcov2()` の重要な互換挙動です。

## 8. 集計式

個別距離 `k` の検体クローン集合を `S_k = {s | d_min(s)=k}` とします。

```text
UniqueClones(LVk) = |S_k|
TotalReads(LVk)   = sum(Read(s) for s in S_k)
Frequency(LVk)    = sum(100 * Read(s) / denominator for s in S_k)
```

累積≤LVkは `S_0 ∪ ... ∪ S_k` に対して同じ式を使います。同じ検体クローンは1つの個別距離にだけ属します。

RG頻度分母は次のとおりです。

- 旧QASAS: 採用in-frameクローンのRead合計。
- Kobe／CDR3のみ: レポートの `In-frame reads` が採用Read以上ならその値。そうでなければ採用Read合計。

CPMは全方式とも採用クローンのRead合計です。ただし方式により必須V/Jやクローン統合単位が異なるため、採用行が異なれば分母も異なり得ます。

## 9. 疑似コード

```text
mode = selected matching mode
sample_clones = load_and_group_sample(sample_file, mode)
database_keys = load_filter_and_group_database(database_file, mode)

for clone in sample_clones:
    candidates = select_candidates(clone, database_keys, mode)
    within_two = []
    for db in candidates:
        distance = levenshtein(clone.cdr3, db.cdr3, maximum=2)
        if distance <= 2:
            within_two.append((db, distance))

    if within_two is empty:
        continue

    minimum = min(distance for db, distance in within_two)
    if mode == legacy:
        retained = within_two
    else:
        retained = [(db, distance) for db, distance in within_two
                    if distance == minimum]
    save clone once with class=minimum and retained DB annotations
```

## 10. 方式間比較の解釈

- 旧QASASとKobeの差は、主にV/J表記処理、CDR3端処理、DB行フィルタ、DB候補保持、RG分母から生じます。
- KobeとCDR3のみの差は、V/J候補制限の有無とクローン定義から生じます。
- CDR3のみ方式は感度が高くなりますが、異なるV/J由来の同一・近似CDR3を抗原特異的候補とする可能性があります。特異度を保証するものではありません。
- DBの版や内容が変われば、同じ検体でも結果は変わります。
- 異なる方式のユニーククローン数を単純な包含関係として解釈しないでください。CDR3のみ方式は母集団のクローン単位が異なります。

## 11. Excelによる監査

各結果の `Method` シートに方式と固定規則、`Input QC` に採用・除外行、頻度分母、DBフィルタ状態、CDR3端判定を保存します。`Matched Clones` には元V/J/CDR3、正規化値、Read、頻度、保持DB候補数、候補距離を保存します。

再現確認では最終グラフだけでなく、これらの中間情報も比較してください。
