@demo @cantonese @web
Feature: 資料集檢視器粵語主要功能示範

  Scenario: 檢查媒體及儲存註解
    Given I begin a recorded demo
    And the dataset viewer is running with a demonstration dataset
    When I open the web application at path "/"
    And I narrate in "yue-HK" for at least 8 seconds:
      """
      資料集檢視器會將媒體同文字註解一齊顯示，亦可以用鍵盤逐項檢查內容。
      """
    Then the current media name and annotation filename are visible
    When I replace the caption with "已檢查示範註解"
    And I move to the next item
    And I return to the previous item
    Then the caption contains "已檢查示範註解"
    When I narrate in "yue-HK" for at least 8 seconds:
      """
      儲存範圍只限目前資料集目錄，外部路徑唔可以覆寫電腦其他位置嘅檔案。
      """
    Then I finish the recorded demo
