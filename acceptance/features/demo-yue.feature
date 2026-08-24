@demo @cantonese @web
Feature: Dataset Annotator 粵語產品介紹

  Scenario: 介紹用鍵盤快速檢查及儲存註解
    Given I begin a recorded demo
    And a fresh acceptance dataset
    And Dataset Annotator is running with a demonstration dataset
    When I open the web application at path "/"
    And I narrate in "yue-HK" for at least 11 seconds:
      """
      呢個係 Dataset Annotator，一個輕量資料標註工具。圖片、影片、聲音或者文字，都可以同相關註解放喺同一個畫面逐項檢查。
      """
    Then the current image, caption editor, and quick-label editor are visible
    When I replace the caption with "已檢查嘅示範圖片"
    And I enter quick label "可以使用"
    And I pause for 2 seconds
    And I press the "ArrowRight" key
    And I narrate in "yue-HK" for at least 10 seconds:
      """
      撳右方向鍵會先儲存註解同快速標籤，再去下一項。撳左方向鍵就可以返轉頭，而頁碼亦可以直接跳去指定項目。
      """
    And I press the "ArrowLeft" key
    Then the caption editor contains "已檢查嘅示範圖片"
    And the quick-label editor contains "可以使用"
    When I narrate in "yue-HK" for at least 10 seconds:
      """
      所有修改都係普通文字檔，而且只會寫入揀選咗嘅資料集。資料夾模式可以標記成個目錄，模板亦可以將參考資料設成唯讀或者隱藏。
      """
    Then I finish the recorded demo
