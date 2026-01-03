(function () {
  function initMarkdownEditors(root) {
    var scope = root || document;
    var textareas = scope.querySelectorAll('textarea[data-md-editor="true"]');

    for (var i = 0; i < textareas.length; i++) {
      var textarea = textareas[i];
      if (textarea.dataset.mdEditorInitialized === 'true') continue;

      // EasyMDE must be loaded first via Media.
      if (typeof EasyMDE === 'undefined') continue;

      textarea.dataset.mdEditorInitialized = 'true';

      new EasyMDE({
        element: textarea,
        autoDownloadFontAwesome: false,
        spellChecker: false,
        status: false,
        toolbar: [
          'bold',
          'italic',
          'heading',
          '|',
          'unordered-list',
          'ordered-list',
          '|',
          'link',
          '|',
          'preview',
          'guide'
        ]
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initMarkdownEditors(document);
  });

  // Django admin inline add event
  document.addEventListener('formset:added', function (event) {
    if (!event || !event.target) return;
    initMarkdownEditors(event.target);
  });
})();
