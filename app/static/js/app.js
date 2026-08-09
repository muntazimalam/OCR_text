document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('dropZone');
  const dropZoneContent = document.getElementById('dropZoneContent');
  const fileInput = document.getElementById('fileInput');
  const gallery = document.getElementById('imageGallery');
  const modal = document.getElementById('inspectModal');
  const closeModalBtn = document.getElementById('closeModal');
  const filterBtns = document.querySelectorAll('.filter-btn');

  let currentFilter = 'all';

  // Drag & Drop
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      uploadFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
      uploadFile(e.target.files[0]);
    }
  });

  // Filter Buttons
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      loadGallery();
    });
  });

  function resetDropZone() {
    const target = dropZoneContent || dropZone;
    target.innerHTML = `
      <div class="upload-icon">📁</div>
      <p><strong>Drag & Drop vehicle image here</strong></p>
      <p class="subtitle">Supports JPG, PNG, WEBP up to 10MB</p>
      <button class="btn-upload" type="button" onclick="document.getElementById('fileInput').click()">Browse Files</button>
    `;
  }

  // Upload Logic
  async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const target = dropZoneContent || dropZone;
      target.innerHTML = '<div class="upload-icon">⏳</div><p>Processing media analysis...</p>';
      const res = await fetch('/api/v1/images', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');

      resetDropZone();
      if (fileInput) fileInput.value = '';

      loadGallery();
      inspectImage(data.id);
    } catch (err) {
      alert('Upload Error: ' + err.message);
      resetDropZone();
      if (fileInput) fileInput.value = '';
    }
  }

  // Quick Sample Analysis
  window.testSample = async function(sampleType) {
    const sampleFiles = {
      'clean': 'clean_plate.jpg',
      'blurry': 'blurry_plate.jpg',
      'dark': 'dark_vehicle.jpg',
      'screenshot': 'screenshot_sample.png'
    };

    const fileName = sampleFiles[sampleType] || 'clean_plate.jpg';
    try {
      const response = await fetch(`/uploads/samples/${fileName}`);
      const blob = await response.blob();
      const file = new File([blob], fileName, { type: blob.type });
      uploadFile(file);
    } catch (err) {
      alert('Failed to load sample image: ' + err.message);
    }
  };

  // Load Gallery
  async function loadGallery() {
    try {
      let url = '/api/v1/images?limit=50';
      if (currentFilter !== 'all') {
        url += `&status=${currentFilter}`;
      }
      const res = await fetch(url);
      const data = await res.json();

      gallery.innerHTML = '';
      if (!data.items || data.items.length === 0) {
        gallery.innerHTML = '<p class="subtitle" style="grid-column: 1/-1; text-align: center; padding: 2rem;">No vehicle images found in pipeline queue.</p>';
        return;
      }

      for (const item of data.items) {
        const card = document.createElement('div');
        card.className = 'image-card';

        // Fetch score if completed
        let scoreTag = `<span class="score-badge score-medium">${item.status}</span>`;
        if (item.status === 'completed') {
          const resResult = await fetch(`/api/v1/images/${item.id}/results`);
          if (resResult.ok) {
            const resData = await resResult.json();
            const score = resData.overall_score !== null ? Math.round(resData.overall_score * 100) : 100;
            const scoreClass = score >= 80 ? 'score-high' : (score >= 50 ? 'score-medium' : 'score-low');
            scoreTag = `<span class="score-badge ${scoreClass}">Score: ${score}%</span>`;
          }
        }

        card.innerHTML = `
          <div class="img-container">
            <img src="/api/v1/images/${item.id}/file" alt="${item.original_filename}" onerror="this.src='https://via.placeholder.com/220x140?text=Processing...'">
            ${scoreTag}
          </div>
          <div class="card-details">
            <div class="file-name">${item.original_filename}</div>
            <div class="meta-row">
              <span>${(item.file_size / 1024).toFixed(1)} KB</span>
              <span>${new Date(item.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
            </div>
          </div>
        `;
        card.addEventListener('click', () => inspectImage(item.id));
        gallery.appendChild(card);
      }
    } catch (err) {
      console.error('Gallery load error:', err);
    }
  }

  // Inspect Image Detail Modal
  async function inspectImage(imageId) {
    try {
      const res = await fetch(`/api/v1/images/${imageId}/results`);
      if (!res.ok) throw new Error('Result not found');
      const data = await res.json();

      document.getElementById('modalImage').src = `/api/v1/images/${imageId}/file`;
      document.getElementById('modalTitle').textContent = `Inspection Report — ${imageId.substring(0, 8)}`;
      
      const scoreDisplay = document.getElementById('scoreDisplay');
      const metricsContainer = document.getElementById('metricsContainer');
      const issuesContainer = document.getElementById('issuesContainer');
      issuesContainer.innerHTML = '';

      if (data.status === 'pending' || data.status === 'processing') {
        scoreDisplay.textContent = '⏳';
        metricsContainer.innerHTML = '<p class="subtitle" style="padding: 1rem; text-align: center;">Media pipeline is currently analyzing this image...</p>';
        issuesContainer.innerHTML = '<div class="issue-chip issue-medium">⏳ Image analysis in progress. Please check back in a few seconds.</div>';
        modal.classList.add('active');
        return;
      }

      if (data.status === 'failed') {
        scoreDisplay.textContent = '❌';
      } else {
        const overallPct = data.overall_score !== null ? Math.round(data.overall_score * 100) : 0;
        scoreDisplay.textContent = `${overallPct}%`;
      }

      const analysis = data.analysis || {};
      const blurInfo = analysis.blur || {};
      const brightInfo = analysis.brightness || {};
      const plateInfo = analysis.number_plate || {};
      const ocrInfo = analysis.ocr || {};
      const metaInfo = analysis.metadata || {};
      const tamperingInfo = analysis.tampering || {};

      metricsContainer.innerHTML = `
        <div class="metric-item">
          <span>Clarity / Blur</span>
          <strong>${blurInfo.is_blurry ? '🔴 Blurry' : '🟢 Sharp'} (Score: ${blurInfo.score || 0})</strong>
        </div>
        <div class="metric-item">
          <span>Brightness / Lighting</span>
          <strong style="text-transform: capitalize;">${brightInfo.status || 'N/A'} (Mean: ${brightInfo.score || 0})</strong>
        </div>
        <div class="metric-item">
          <span>License Plate Regex</span>
          <strong>${plateInfo.valid ? '🟢 Valid (' + (plateInfo.confidence ? Math.round(plateInfo.confidence * 100) + '%' : '90%') + ')' : '🔴 Invalid / Not Detected'}</strong>
        </div>
        <div class="metric-item">
          <span>OCR Scene Text</span>
          <strong>${ocrInfo.text || 'None detected'}</strong>
        </div>
        <div class="metric-item">
          <span>Screenshot Prob.</span>
          <strong>${metaInfo.screenshot_probability ? Math.round(metaInfo.screenshot_probability * 100) + '%' : '0%'}</strong>
        </div>
        <div class="metric-item">
          <span>Metadata Editing</span>
          <strong>${tamperingInfo.suspicious_editing ? '⚠️ Editing Software Flagged' : '🟢 Clean Camera EXIF'}</strong>
        </div>
      `;

      if (data.status === 'failed') {
        issuesContainer.innerHTML = `<div class="issue-chip issue-high">🔴 <strong>Processing Failed</strong>: ${data.error_message || 'Image failed validation checks or license plate detection.'}</div>`;
      }

      if (data.issues && data.issues.length > 0) {
        data.issues.forEach(issue => {
          const issueClass = issue.severity === 'high' ? 'issue-high' : (issue.severity === 'medium' ? 'issue-medium' : 'issue-low');
          issuesContainer.innerHTML += `
            <div class="issue-chip ${issueClass}">
              ⚠️ <strong>${issue.type}</strong>: ${issue.description}
            </div>
          `;
        });
      } else if (data.status === 'completed') {
        issuesContainer.innerHTML = '<div class="issue-chip issue-low">🟢 No quality or authenticity issues detected.</div>';
      }

      modal.classList.add('active');
    } catch (err) {
      alert('Inspection Error: ' + err.message);
    }
  }

  closeModalBtn.addEventListener('click', () => modal.classList.remove('active'));
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('active');
  });

  loadGallery();
});
