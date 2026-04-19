# cdcasasagi add --write

`--write` の round-trip (設定ファイル書き込み / .bak 作成 / revert) のE2E

## add --write は設定ファイルと .bak を作成する

* MCPサーバ設定なしでClaude Desktopが使われている
* cdcasasagiで"add https://mcp.notion.com/mcp --write"を実行する
* 設定ファイルに"notion"エントリが書き込まれている
* バックアップファイルが作成されている

## 2回目の --write は直前の状態を .bak に残す

* MCPサーバ設定なしでClaude Desktopが使われている
* cdcasasagiで"add https://mcp.notion.com/mcp --write"を実行する
* 設定ファイルに"notion"エントリが書き込まれている
* cdcasasagiで"add https://developers.openai.com/mcp --write"を実行する
* 設定ファイルに"notion,developers"エントリが書き込まれている
* バックアップファイルに"notion"エントリが書き込まれている

## 既存エントリとの衝突は --force なしで失敗する

* MCPサーバ設定なしでClaude Desktopが使われている
* cdcasasagiで"add https://mcp.notion.com/mcp --write"を実行する
* 設定ファイルに"notion"エントリが書き込まれている
* cdcasasagiで"add https://mcp.notion.com/mcp --write"を実行する
* 直前のコマンドは失敗する
* 設定ファイルは直前の書き込みから変更されていない

## 同一URLを別名で --write すると失敗する

* MCPサーバ設定なしでClaude Desktopが使われている
* cdcasasagiで"add https://mcp.notion.com/mcp --write"を実行する
* 設定ファイルに"notion"エントリが書き込まれている
* cdcasasagiで"add https://mcp.notion.com/mcp --name my-notion --write"を実行する
* 直前のコマンドは失敗する
* 設定ファイルは直前の書き込みから変更されていない

## --force を付けると別名にリネームされる

* MCPサーバ設定なしでClaude Desktopが使われている
* cdcasasagiで"add https://mcp.notion.com/mcp --write"を実行する
* 設定ファイルに"notion"エントリが書き込まれている
* cdcasasagiで"add https://mcp.notion.com/mcp --name my-notion --write --force"を実行する
* 設定ファイルに"my-notion"エントリが書き込まれている
* 設定ファイル内"my-notion"のURLは"https://mcp.notion.com/mcp"である

## revert はバックアップファイルの状態に戻す

* MCPサーバ設定なしでClaude Desktopが使われている
* cdcasasagiで"add https://mcp.notion.com/mcp --write"を実行する
* cdcasasagiで"add https://developers.openai.com/mcp --write"を実行する
* 設定ファイルに"notion,developers"エントリが書き込まれている
* cdcasasagiで"revert"を実行する
* 設定ファイルに"notion"エントリが書き込まれている
