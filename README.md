# EarthScienceExperiment

## 概要
　これは，2021年度前期地球科学実験の「地震」の受講者が，観測波形をフォーマット変換したり，波形を描画したりするためのサンプルコードです。Python及びGoogle Collaboratoryを使用しています。

## 使用手順
- 共有ドライブ `EarthScienceExperiment` のショートカットを作成

[各notebookで次の操作]
1. ドライブのマウント
  ```python
  from google.colab import drive
  drive.mount('/content/drive') 
  ```
  指示されたURLを開いてアクセスを許可，パスをセルの標準入力に貼り付ける

2. フォルダのパス設定
  a. 左側のタブ`ファイル`から`EarthScienceExperiment`という名前のフォルダを探す（作成したショートカット）
  b. フォルダ上で右クリックして「パスをコピー」を選択
  c. 下の`projectBaseDir`にパスを貼り付ける

## 注意事項
- この共有ドライブ内のコード等を使用したことによって生じるいかなる損害も，著者は責任を負いません
