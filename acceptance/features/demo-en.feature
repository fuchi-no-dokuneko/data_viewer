@demo @english @web
Feature: English key-feature demonstration of the dataset viewer

  Scenario: Review media and save its annotation
    Given I begin a recorded demo
    And the dataset viewer is running with a demonstration dataset
    When I open the web application at path "/"
    And I narrate in "en-US" for at least 8 seconds:
      """
      The dataset viewer keeps the media and its text annotations together, with keyboard navigation for moving through each item.
      """
    Then the current media name and annotation filename are visible
    When I replace the caption with "reviewed demonstration caption"
    And I move to the next item
    And I return to the previous item
    Then the caption contains "reviewed demonstration caption"
    When I narrate in "en-US" for at least 8 seconds:
      """
      Saving is limited to the selected dataset directory, so a submitted parent path cannot overwrite files elsewhere on the computer.
      """
    Then I finish the recorded demo
