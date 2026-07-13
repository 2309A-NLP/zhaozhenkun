const providerSelect = document.getElementById('model_provider');
const reviewProviderSelect = document.getElementById('review_provider');
const refreshReviewButton = document.getElementById('refresh_review');
const detailReviewLink = document.getElementById('detail_review_link');
const importDialog = document.getElementById('import_dialog');
const importButton = document.getElementById('open_import');
const closeImportButton = document.getElementById('close_import');
const importForm = document.getElementById('import_form');
const detailForm = document.getElementById('detail_form');
const audioForm = document.getElementById('audio_form');

function currentProvider() {
  if (providerSelect) {
    localStorage.setItem('interview_provider', providerSelect.value);
    return providerSelect.value;
  }
  return localStorage.getItem('interview_provider') || document.body.dataset.defaultProvider || 'deepseek';
}

if (providerSelect) {
  providerSelect.value = localStorage.getItem('interview_provider') || providerSelect.value;
  providerSelect.addEventListener('change', () => localStorage.setItem('interview_provider', providerSelect.value));
  document.querySelectorAll('.review-link').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const target = `/reviews/${link.dataset.id}?provider=${currentProvider()}`;
      window.location.href = target;
    });
  });
}

if (detailReviewLink) {
  detailReviewLink.addEventListener('click', (event) => {
    event.preventDefault();
    window.location.href = `/reviews/${detailReviewLink.href.split('/').pop()}?provider=${currentProvider()}`;
  });
}

if (reviewProviderSelect) {
  reviewProviderSelect.addEventListener('change', () => {
    const target = `/reviews/${reviewProviderSelect.dataset.id}?provider=${reviewProviderSelect.value}`;
    localStorage.setItem('interview_provider', reviewProviderSelect.value);
    window.location.href = target;
  });
}

if (importButton && importDialog) {
  importButton.addEventListener('click', () => importDialog.showModal());
}

if (closeImportButton && importDialog) {
  closeImportButton.addEventListener('click', () => importDialog.close());
}

if (importForm) {
  importForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = document.getElementById('import_message');
    try {
      const rows = JSON.parse(document.getElementById('import_rows').value);
      const reporterName = document.getElementById('reporter_name').value;
      const response = await fetch('/api/interviews/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows, reporter_name: reporterName }),
      });
      const result = await response.json();
      message.textContent = result.message;
      if (result.ok) {
        window.setTimeout(() => window.location.reload(), 800);
      }
    } catch (error) {
      message.textContent = `导入失败：${error.message}`;
    }
  });
}

if (detailForm) {
  detailForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = document.getElementById('detail_message');
    const formData = new FormData(detailForm);
    const payload = Object.fromEntries(formData.entries());
    const response = await fetch(`/api/interviews/${detailForm.dataset.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    message.textContent = result.message;
    if (result.ok) {
      window.setTimeout(() => window.location.reload(), 800);
    }
  });
}

if (audioForm) {
  audioForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = document.getElementById('audio_message');
    const formData = new FormData(audioForm);
    const response = await fetch(`/api/interviews/${audioForm.dataset.id}/audio`, {
      method: 'POST',
      body: formData,
    });
    const result = await response.json();
    message.textContent = result.message || '处理完成';
    if (result.ok) {
      window.setTimeout(() => window.location.reload(), 800);
    }
  });
}

if (refreshReviewButton) {
  refreshReviewButton.addEventListener('click', async () => {
    const message = document.getElementById('refresh_review_message');
    message.textContent = '正在重新生成复盘，请稍候...';
    const provider = reviewProviderSelect ? reviewProviderSelect.value : currentProvider();
    const response = await fetch(`/api/reviews/${refreshReviewButton.dataset.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, refresh: true }),
    });
    const result = await response.json();
    message.textContent = result.message || (result.ok ? '复盘已重新生成。' : '复盘生成失败。');
    if (result.ok) {
      window.setTimeout(() => {
        window.location.href = `/reviews/${refreshReviewButton.dataset.id}?provider=${provider}`;
      }, 800);
    }
  });
}
