# 立体ガラス彫刻

完成モデル：[butterfly_sculpture.blend](butterfly_sculpture.blend)  
完成画像：[2048×2048](renders/final.png)  
確認資料：[参考との比較](review/images/comparison.png)・[各視点](review/images/views.png)  
検証結果：[verification.json](review/reports/verification.json)

## 再生成

Linux、Blender 5.2.2、Python 3、Pillow、DejaVu Sansが必要です。追加のBlenderアドオンは使いません。

```sh
/usr/bin/python3 scripts/run.py all
```

ワークスペースのルートからは次のコマンドを使います。

```sh
/usr/bin/python3 stained_glass_butterfly_sculpture/scripts/run.py all
```

`build` → `validate` → `preview` → `final` → `verify` の順で実行します。
単工程は `all` を工程名に置き換えます。`preview --views main` は主構図だけの確認、
`--threads 8` はCPUスレッド数の変更です。最終描画前に現行シーンの全確認視点が必要です。

描画はCycles CPU、確認1024角・64サンプル、完成2048角・512サンプル、AgX、
最大16バウンス・透過12バウンス、適応サンプリングとOpenImageDenoiseを使います。
バックグラウンド実行の音声環境はスクリプトが設定します。

## 編集

色ガラス・縁取り・装飾・撮影環境をコレクションごとに分けています。
ガラスは閉じたメッシュ、縁取り・触角・波の制御用形状はカーブで編集できます。
参考画像は `.blend` にパックされ、`Reference_Guides` 内で描画・表示を隠しています。
カメラは main・side・rear・top。完成画像のカメラは `Camera · main` です。
全体高さは相対比率で約30 cmに設定しています。

`Editable_Spines` には波や水滴の制御用カーブを保持しています。
生成時の制御点と断面は `scripts/build_scene.py` に記載しています。
保存した制御カーブは参照用です。波を再生成する場合はスクリプトの制御点を変更します。
蝶は主役1匹と小さい3匹。小さい蝶は主役のガラス区画を共有したインスタンスです。
主画像を構図の基準、angles画像を奥行きの補助資料として使っています。
羽は淡いオパールガラス、波は透過ガラスです。小さな蝶の吸収濃度は縮尺に合わせて調整しています。
スタジオには背景の明度勾配、反射用の黒いカード、細長い照明を設けています。
集光は波と水滴を対象に、背後の小さな光源から計算します。
羽の細かな区画と内部のきらめきは、参考画像をもとにした幾何形状と微粒子で近似しています。

## 確認資料

`review/logs/` に工程ログ、`review/reports/` に形状・参照の整合性と描画条件を保存します。
検証では閉じた体積、外向きの法線、羽のガラス区画の厚みも確認します。
全確認視点が揃うと `preview_comparison.png` と `views.png` を作成します。
出力ファイル名は固定で、再実行で更新します。描画成功後に画像を置換し、検証では
シーンと画像のSHA-256を照合します。カメラ・材質を変更した場合は保存後に
`validate`、`preview`、`final`、`verify` を順に実行してください。
