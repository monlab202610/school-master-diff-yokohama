# スキーマ v1

単位は、指定版に掲載された1学校コードの属性行。学校コードをキーとし、現存校の認定や在籍の判断はしません。

| 列 | 型・原典との対応 |
| --- | --- |
| school_code | 英字1字＋数字12字の13文字。学校コード。再付番やチェックディジットの検証はしない |
| school_type | 学校種のコード部分。B1小学校、C1中学校、C2義務教育学校 |
| prefecture_code | 都道府県番号の2文字。このサンプルは14 |
| establishment_type | 設置区分のコード文字列。1国、2公、3私 |
| branch_status | 本分校のコード文字列。1本、2分、9廃。原典の属性として保持 |
| school_name、address | 学校名、学校所在地の原文。NFKC・住所分解・名前の名寄せはしない |
| postal_code | 7文字数字またはnull。先頭ゼロを保つ |
| attribute_set_date、attribute_retired_date | 属性情報設定/廃止年月日。実在日付を検証しYYYY-MM-DDに統一、空欄はnull。閉校の実日と断定しない |
| legacy_survey_code | 旧学校調査番号、文字列またはnull。実例14C012のように英字を含む。学校コードと別の体系 |
| successor_school_code | 移行後の学校コード、文字列またはnull。原典に書かれていない関係は補完しない |
| *_raw（4列） | 学校種・都道府県番号・設置区分・本分校の原文ラベル |
| source_file_id | provenance.jsonのファイルID |
| source_record_number | 原典CSVの1始まり論理行番号。引用フィールド内に改行があるため物理行と異なる |
| source_values（JSONだけ） | 原典12列の値を残した辞書。CSVには入れない |

CSVはUTF-8 BOMなし、LF、標準CSV引用。原典空欄はCSV空欄/JSON nullで、0や「不存在」ではありません。source_record_numberだけ整数、それ以外のコードは文字列です。

changes.jsonは、before/after版の情報、summary、changes、date_format_only_codesを持ちます。changesの各項目にはschool_code、change_kind、changed_fields、before、afterがあります。

- added_to_source / absent_from_source：対応する版の東日本原典に存在/不在。新設/閉校の認定ではない。
- entered_scope / left_scope：同じコードが原典に残り、この抽出範囲に出入り。追加/不在と区別する。
- same_code_attributes_changed：日付を正規化した後の原典属性の差。
- date_format_only_codes：日付表記だけが異なり、正規化後の比較属性が一致したコード。取り込みの変更候補から分離。

changed_fieldsは主要11属性（school_code以外）の差で、出典行・文字コード・原文日付表記の差を含めません。rawラベルも保存しますが、名称だけによる自動マッチングは行いません。
