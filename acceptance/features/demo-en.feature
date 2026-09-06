@demo @english @web
Feature: English product introduction for Dataset Annotator

  Scenario: Introduce a keyboard-first annotation review
    Given I begin a recorded demo
    And a fresh acceptance dataset
    And Dataset Annotator is running with a demonstration dataset
    When I open the web application at path "/"
    And I narrate in "en-US" for at least 11 seconds:
      """
      This is Dataset Annotator, a lightweight browser workspace for reviewing images, video, audio, or text beside their annotation files. The current item and its editable labels stay together on one screen.
      """
    Then the current image, caption editor, and quick-label editor are visible
    When I replace the caption with "a reviewed sample image"
    And I enter quick label "ready"
    And I pause for 2 seconds
    And I press the "ArrowRight" key
    And I narrate in "en-US" for at least 10 seconds:
      """
      The right arrow saves both edits and advances immediately. The left arrow returns, while the page number can jump directly to another item in a large dataset.
      """
    And I press the "ArrowLeft" key
    Then the caption editor contains "a reviewed sample image"
    And the quick-label editor contains "ready"
    When I narrate in "en-US" for at least 10 seconds:
      """
      Saved annotations remain ordinary files inside the selected dataset directory. Directory mode can apply one quick label to a whole folder, and templates can keep reference metadata read-only or hidden.
      """
    Then I finish the recorded demo
