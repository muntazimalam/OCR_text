// ─── Toast System ─────────────────────────────────────────────────────────────
function showToast(message, type = 'info', durationMs = 3500) {
  const container = document.getElementById('toast-container');
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span style="font-size:1rem">${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('hiding');
    setTimeout(() => toast.remove(), 280);
  }, durationMs);
}

// ─── Safe JSON parser ──────────────────────────────────────────────────────────
async function parseResponse(res) {
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return await res.json();
  const text = await res.text();
  throw new Error(`Server error ${res.status}: ${res.statusText || text.substring(0, 80)}`);
}

// ─── SVG Score Ring ────────────────────────────────────────────────────────────
function animateScoreRing(pct) {
  const fill = document.getElementById('scoreRingFill');
  const display = document.getElementById('scoreDisplay');
  if (!fill) return;
  const circumference = 2 * Math.PI * 35; // r=35 → ≈219.9
  const offset = circumference - (pct / 100) * circumference;
  const color = pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
  fill.style.strokeDasharray = circumference;
  fill.style.strokeDashoffset = offset;
  fill.style.stroke = color;
  display.style.color = color;
  display.textContent = `${pct}%`;
}

function resetScoreRing(symbol = '—') {
  const fill = document.getElementById('scoreRingFill');
  const display = document.getElementById('scoreDisplay');
  if (fill) { fill.style.strokeDashoffset = 220; fill.style.stroke = 'var(--accent-success)'; }
  if (display) { display.style.color = 'var(--text-subtle)'; display.textContent = symbol; }
}

// ─── Skeleton Loaders ─────────────────────────────────────────────────────────
function showSkeletons(count = 4) {
  const gallery = document.getElementById('imageGallery');
  gallery.innerHTML = Array.from({ length: count }, () => `
    <div class="skeleton-card">
      <div class="skeleton skeleton-img"></div>
      <div class="skeleton skeleton-line"></div>
      <div class="skeleton skeleton-line-sm"></div>
    </div>`).join('');
}

// ─── Stats Banner ─────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const res = await fetch('/api/v1/images/stats');
    if (!res.ok) return;
    const d = await parseResponse(res);
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.classList.remove('skeleton');
      el.style.cssText = '';
      el.textContent = val;
    };
    set('statTotal',    d.total ?? '—');
    set('statCompleted', d.completed ?? '—');
    set('statFailed',   d.failed ?? '—');
    set('statPending',  d.pending ?? '—');
    set('statPassRate', d.total > 0 ? `${Math.round(d.pass_rate * 100)}%` : '—');
  } catch (e) {
    console.warn('Stats load failed:', e.message);
  }
}

// ─── Main App ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('dropZone');
  const dropZoneContent = document.getElementById('dropZoneContent');
  const fileInput = document.getElementById('fileInput');
  const gallery = document.getElementById('imageGallery');
  const modal = document.getElementById('inspectModal');
  const closeModalBtn = document.getElementById('closeModal');
  const filterBtns = document.querySelectorAll('.filter-btn');
  const browseBtn = document.getElementById('browseBtn');

  let currentFilter = 'all';
  let inspectPollTimer = null;

  // Initial data load
  loadStats();
  loadGallery();

  // Browse button
  browseBtn?.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

  // ─── Drag & Drop ──────────────────────────────────────────────────────────
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) uploadFile(e.target.files[0]);
  });

  // ─── Filter Buttons ────────────────────────────────────────────────────────
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      loadGallery();
    });
  });

  // ─── Drop Zone Reset ───────────────────────────────────────────────────────
  function resetDropZone() {
    const target = dropZoneContent || dropZone;
    target.innerHTML = `
      <span class="upload-icon" aria-hidden="true">📁</span>
      <p><strong>Drag &amp; Drop vehicle image here</strong></p>
      <p class="subtitle">Supports JPG, PNG, WEBP · Max 10MB</p>
      <button class="btn-upload" type="button" id="browseBtn">Browse Files</button>
    `;
    document.getElementById('browseBtn')?.addEventListener('click', () => fileInput.click());
  }

  // ─── Upload Logic ──────────────────────────────────────────────────────────
  async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    const target = dropZoneContent || dropZone;
    target.innerHTML = `<span class="upload-icon">⏳</span><p>Uploading &amp; queuing analysis...</p>`;

    try {
      const res = await fetch('/api/v1/images', { method: 'POST', body: formData });
      const data = await parseResponse(res);
      if (!res.ok) throw new Error(data.detail || 'Upload failed');

      resetDropZone();
      if (fileInput) fileInput.value = '';
      showToast(`✔ "${file.name}" queued for analysis`, 'success');
      loadGallery();
      loadStats();
      inspectImage(data.id);
    } catch (err) {
      console.error('Upload Error:', err);
      target.innerHTML = `
        <span class="upload-icon">⚠️</span>
        <p><strong style="color:#ff8e8e">Upload Failed</strong></p>
        <p class="subtitle">${err.message}</p>
        <button class="btn-upload" type="button" id="browseBtn">Try Again</button>
      `;
      document.getElementById('browseBtn')?.addEventListener('click', () => fileInput.click());
      if (fileInput) fileInput.value = '';
      showToast(err.message, 'error');
    }
  }

  // ─── Quick Sample Analysis ─────────────────────────────────────────────────
  window.testSample = async function(sampleType) {
    const sampleFiles = {
      'clean': 'clean_plate.jpg',
      'blurry': 'blurry_plate.jpg',
      'dark': 'dark_vehicle.jpg',
      'screenshot': 'screenshot_sample.png'
    };
    const fileName = sampleFiles[sampleType] || 'clean_plate.jpg';
    try {
      showToast(`Loading sample: ${fileName}...`, 'info', 2000);
      const response = await fetch(`/uploads/samples/${fileName}`);
      if (!response.ok) throw new Error(`Sample not found: ${fileName}`);
      const blob = await response.blob();
      const file = new File([blob], fileName, { type: blob.type });
      uploadFile(file);
    } catch (err) {
      showToast(`Failed to load sample: ${err.message}`, 'error');
    }
  };

  // ─── Delete Image ──────────────────────────────────────────────────────────
  async function deleteImage(imageId, filename, e) {
    e.stopPropagation();
    if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;
    try {
      const res = await fetch(`/api/v1/images/${imageId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Delete failed');
      showToast(`"${filename}" deleted`, 'success');
      loadGallery();
      loadStats();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  // ─── Gallery Load ──────────────────────────────────────────────────────────
  async function loadGallery() {
    showSkeletons(6);
    try {
      let url = '/api/v1/images?limit=50';
      if (currentFilter !== 'all') url += `&status=${currentFilter}`;
      const res = await fetch(url);
      const data = await parseResponse(res);

      gallery.innerHTML = '';
      if (!data.items || data.items.length === 0) {
        gallery.innerHTML = `<p class="subtitle" style="grid-column:1/-1; text-align:center; padding:3rem 0;">
          No vehicle images found in pipeline queue.</p>`;
        return;
      }

      for (const item of data.items) {
        const card = document.createElement('div');
        card.className = 'image-card';

        let scoreTag = `<span class="score-badge score-medium">${item.status}</span>`;
        if (item.status === 'completed') {
          const score = (item.overall_score != null) ? Math.round(item.overall_score * 100) : 100;
          const cls = score >= 80 ? 'score-high' : score >= 50 ? 'score-medium' : 'score-low';
          scoreTag = `<span class="score-badge ${cls}">Score: ${score}%</span>`;
        } else if (item.status === 'failed') {
          scoreTag = `<span class="score-badge score-low">Failed</span>`;
        } else if (item.status === 'processing') {
          scoreTag = `<span class="score-badge score-medium">⚙️ Processing</span>`;
        }

        const res_px = item.width && item.height ? `${item.width}×${item.height}` : '';
        card.innerHTML = `
          <button class="delete-btn" title="Delete image" aria-label="Delete ${item.original_filename}">🗑 Delete</button>
          <div class="img-container">
            <img src="/api/v1/images/${item.id}/file" alt="${item.original_filename}" loading="lazy"
                 onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'80\\' height=\\'80\\' viewBox=\\'0 0 24 24\\'%3E%3Cpath fill=\\'%2364748b\\' d=\\'M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z\\'/%3E%3C/svg%3E'">
            ${scoreTag}
          </div>
          <div class="card-details">
            <div class="file-name" title="${item.original_filename}">${item.original_filename}</div>
            <div class="meta-row">
              <span>${(item.file_size / 1024).toFixed(1)} KB ${res_px ? '· ' + res_px : ''}</span>
              <span>${new Date(item.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
            </div>
          </div>`;

        card.querySelector('.delete-btn').addEventListener('click', (e) => deleteImage(item.id, item.original_filename, e));
        card.addEventListener('click', () => inspectImage(item.id));
        gallery.appendChild(card);
      }
    } catch (err) {
      gallery.innerHTML = `<p class="subtitle" style="grid-column:1/-1; text-align:center; padding:2rem; color:var(--accent-danger)">
        Failed to load gallery: ${err.message}</p>`;
      console.error('Gallery load error:', err);
    }
  }

  // ─── Stop Polling ─────────────────────────────────────────────────────────
  function stopModalPolling() {
    if (inspectPollTimer) { clearTimeout(inspectPollTimer); inspectPollTimer = null; }
  }

  // ─── Inspect Modal ────────────────────────────────────────────────────────
  async function inspectImage(imageId) {
    stopModalPolling();
    resetScoreRing('⏳');
    document.getElementById('metricsContainer').innerHTML = '';
    document.getElementById('issuesContainer').innerHTML = '';
    document.getElementById('modalTitle').textContent = `Inspection Report — ${imageId.substring(0, 8)}`;
    document.getElementById('modalImage').src = `/api/v1/images/${imageId}/file`;
    modal.classList.add('active');

    try {
      const res = await fetch(`/api/v1/images/${imageId}/results`);
      if (!res.ok) throw new Error('Result not found');
      const data = await parseResponse(res);

      const metricsContainer = document.getElementById('metricsContainer');
      const issuesContainer = document.getElementById('issuesContainer');

      if (data.status === 'pending' || data.status === 'processing') {
        resetScoreRing('⏳');
        metricsContainer.innerHTML = `<p class="subtitle" style="padding:0.75rem 0; text-align:center;">
          Pipeline is analyzing this image...</p>`;
        issuesContainer.innerHTML = `<div class="issue-chip issue-medium">
          ⏳ Analysis in progress — updating automatically...</div>`;
        inspectPollTimer = setTimeout(() => { inspectImage(imageId); loadGallery(); loadStats(); }, 2500);
        return;
      }

      if (data.status === 'failed') {
        resetScoreRing('❌');
        document.getElementById('scoreDisplay').style.color = 'var(--accent-danger)';
      } else {
        const pct = data.overall_score != null ? Math.round(data.overall_score * 100) : 0;
        animateScoreRing(pct);
      }

      const a = data.analysis || {};
      const blur       = a.blur || {};
      const bright     = a.brightness || {};
      const plate      = a.number_plate || {};
      const ocr        = a.ocr || {};
      const meta       = a.metadata || {};
      const tampering  = a.tampering || {};

      const contrastTxt = bright.contrast_score != null
        ? ` · Contrast: ${Math.round(bright.contrast_score)}` : '';

      metricsContainer.innerHTML = `
        <div class="metric-item">
          <span>Clarity / Blur</span>
          <strong>${blur.is_blurry ? '🔴 Blurry' : '🟢 Sharp'} (${blur.score ?? 0})</strong>
        </div>
        <div class="metric-item">
          <span>Brightness / Lighting</span>
          <strong style="text-transform:capitalize;">${bright.status || 'N/A'} (${bright.score ?? 0}${contrastTxt})</strong>
        </div>
        <div class="metric-item">
          <span>License Plate</span>
          <strong>${plate.valid
            ? `🟢 Valid (${plate.confidence ? Math.round(plate.confidence * 100) + '%' : '90%'})`
            : '🔴 Not Detected'}</strong>
        </div>
        <div class="metric-item">
          <span>OCR Scene Text</span>
          <strong>${ocr.text || 'None detected'}</strong>
        </div>
        <div class="metric-item">
          <span>Screenshot Probability</span>
          <strong>${meta.screenshot_probability ? Math.round(meta.screenshot_probability * 100) + '%' : '0%'}</strong>
        </div>
        <div class="metric-item">
          <span>Metadata / EXIF</span>
          <strong>${tampering.suspicious_editing ? '⚠️ Editing Software Flagged' : '🟢 Clean Camera EXIF'}</strong>
        </div>`;

      issuesContainer.innerHTML = '';
      if (data.status === 'failed') {
        issuesContainer.innerHTML += `<div class="issue-chip issue-high">
          🔴 <strong>Processing Failed</strong>: ${data.error_message || 'Validation checks failed.'}</div>`;
      }

      if (data.issues?.length > 0) {
        data.issues.forEach(issue => {
          const cls = issue.severity === 'high' ? 'issue-high' : issue.severity === 'medium' ? 'issue-medium' : 'issue-low';
          issuesContainer.innerHTML += `<div class="issue-chip ${cls}">
            ⚠️ <strong>${issue.type}</strong>: ${issue.description}</div>`;
        });
      } else if (data.status === 'completed') {
        issuesContainer.innerHTML = `<div class="issue-chip issue-low">🟢 No quality or authenticity issues detected.</div>`;
      }

    } catch (err) {
      stopModalPolling();
      resetScoreRing('⚠️');
      document.getElementById('metricsContainer').innerHTML =
        `<p class="subtitle" style="padding:0.75rem;color:var(--accent-danger)">Unable to load details.</p>`;
      document.getElementById('issuesContainer').innerHTML =
        `<div class="issue-chip issue-high">⚠️ <strong>Error</strong>: ${err.message}</div>`;
    }
  }

  // ─── Modal Close ───────────────────────────────────────────────────────────
  closeModalBtn.addEventListener('click', () => { stopModalPolling(); modal.classList.remove('active'); });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) { stopModalPolling(); modal.classList.remove('active'); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
      stopModalPolling();
      modal.classList.remove('active');
    }
  });
});
