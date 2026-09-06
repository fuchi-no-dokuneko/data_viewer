@daily @uat @web
Feature: Daily human and agent acceptance of Dataset Annotator
  An annotator must review every supported media type, save labels, recover
  their position, and stay inside the configured dataset directory.

  Background:
    Given a fresh acceptance dataset

  Scenario: Password login moves from rejection to an authenticated workspace
    Given Dataset Annotator is running with password protection
    When I open the web application at path "/"
    Then the login form is shown
    When I submit password "wrong-password"
    Then the login error says "Invalid password"
    When I submit password "uat-secret"
    Then the annotator workspace is shown
    And the current media file loads after authentication

  Scenario: Protected API and media requests reject an anonymous user
    Given Dataset Annotator is running with password protection
    When I request API path "/api/item/0" without a session
    Then the HTTP response status is 401
    When I request media path "/file/group-a/01-image.png" without a session
    Then the HTTP response redirects to "/login"

  Scenario: Every supported media type has the expected preview
    Given Dataset Annotator is running with login disabled
    When I open the web application at path "/"
    Then item 1 shows an "image" preview for "group-a/01-image.png"
    And the image resolution is visible
    When I press the "ArrowRight" key
    Then item 2 shows a "video" preview for "group-a/02-video.mp4"
    When I press the "ArrowRight" key
    Then item 3 shows an "audio" preview for "group-b/03-audio.mp3"
    When I press the "ArrowRight" key
    Then item 4 shows a "text" preview for "group-b/04-note.txt"
    And the text preview contains "acceptance note"

  Scenario: Caption and quick-label changes survive navigation and reload
    Given Dataset Annotator is running with login disabled
    When I open the web application at path "/"
    And I replace the caption with "daily accepted caption"
    And I enter quick label "approved"
    And I press the "ArrowRight" key
    Then annotation file "group-a/01-image.caption_txt" contains "daily accepted caption"
    And annotation file "group-a/01-image.system_label_meta_txt" contains "approved"
    When I press the "ArrowLeft" key
    Then the caption editor contains "daily accepted caption"
    And the quick-label editor contains "approved"
    When I reload the page
    Then the caption editor contains "daily accepted caption"
    And the quick-label editor contains "approved"

  Scenario: Number navigation clamps input and restores the last viewed item
    Given Dataset Annotator is running with login disabled
    When I open the web application at path "/"
    And I jump to item 3
    Then the page number is 3 of 4
    When I reload the page
    Then the page number is 3 of 4
    When I jump to item 99
    Then the page number is 4 of 4
    When I submit an empty page number
    Then item "group-b/04-note.txt" remains displayed with an empty page number
    When I jump to item 4
    Then the page number is 4 of 4

  Scenario: Previous and next navigation wrap at dataset boundaries
    Given Dataset Annotator is running with login disabled
    When I open the web application at path "/"
    And I press the "ArrowLeft" key
    Then the page number is 4 of 4
    When I press the "ArrowRight" key
    Then the page number is 1 of 4

  Scenario: Directory mode saves one label and moves between directories
    Given Dataset Annotator is running in directory mode
    When I open the web application at path "/"
    Then the "DIR MODE" badge is visible
    And the quick-label filename is "group-a/system_label_dir_meta_txt"
    When I enter quick label "group-a accepted"
    And I press the "ArrowRight" key
    Then annotation file "group-a/system_label_dir_meta_txt" contains "group-a accepted"
    When I press the "ArrowDown" key
    Then item 3 shows an "audio" preview for "group-b/03-audio.mp3"
    And the quick-label filename is "group-b/system_label_dir_meta_txt"
    When I press the "ArrowUp" key
    And I reload the page
    Then item 1 shows an "image" preview for "group-a/01-image.png"
    And the quick-label editor contains "group-a accepted"

  Scenario: Debug mode gives an explicit visible state
    Given Dataset Annotator is running in debug mode
    When I open the web application at path "/"
    Then the "DEBUG" badge is visible

  Scenario: A template separates editable, summarized, and hidden annotations
    Given Dataset Annotator is running with the acceptance template
    When I open the web application at path "/"
    Then the caption annotation remains editable
    And the metadata summary shows "Author" with value "Ada"
    And the private annotation is hidden
    And the hidden badge says "HIDDEN 1"

  Scenario: Save validation rejects malformed and escaping annotation requests
    Given Dataset Annotator is running with login disabled
    When I POST an annotation for "../outside.txt" with text "escaped"
    Then the HTTP response status is 400
    And no file was created outside the dataset directory
    When I POST malformed JSON to "/api/item/0"
    Then the HTTP response status is 400

  Scenario: Missing items and escaping media paths are not served
    Given Dataset Annotator is running with login disabled
    When I request API path "/api/item/999" without a session
    Then the HTTP response status is 404
    When I request API path "/file/%2E%2E/outside.txt" without a session
    Then the HTTP response status is 404
