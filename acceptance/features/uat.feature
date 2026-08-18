@daily @uat @web
Feature: Daily acceptance of the dataset viewer
  An annotator can inspect and save dataset labels while all file access stays
  inside the configured dataset directory.

  Scenario: View and update an annotation
    Given a temporary dataset contains "sample.txt" and "sample.caption_txt"
    And the dataset viewer is running for that temporary dataset with login disabled
    When I open the web application at path "/"
    Then the page shows "sample.txt"
    And the annotation editor shows "sample.caption_txt"
    When I replace the caption with "daily accepted caption"
    And I move to the next item
    Then "sample.caption_txt" contains "daily accepted caption"

  Scenario: Reject a path outside the configured dataset
    Given the dataset viewer is running for a temporary dataset with login disabled
    When I POST JSON to "/api/item/0" with annotation filename "../outside.txt"
    Then the HTTP response status is 400
    And "outside.txt" was not created outside the dataset directory

  Scenario: Require login for media when a password is configured
    Given the dataset viewer is running with a password
    And I have not logged in
    When I request the current media file directly
    Then I am redirected to the login page
