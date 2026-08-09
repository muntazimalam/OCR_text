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
  const circumference = 2 * Math.PI * 44; // r=44 → ≈276.46
  const offset = circumference - (pct / 100) * circumference;
  const color = pct >= 80 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171';
  fill.style.strokeDasharray = circumference;
  fill.style.strokeDashoffset = offset;
  fill.style.stroke = color;
  if (display) {
    display.style.color = color;
    display.textContent = `${pct}%`;
  }
}

function resetScoreRing(symbol = '—') {
  const fill = document.getElementById('scoreRingFill');
  const display = document.getElementById('scoreDisplay');
  if (fill) { fill.style.strokeDashoffset = 276.46; fill.style.stroke = 'var(--accent-success)'; }
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

// ─── Animated Count-Up ───────────────────────────────────────────────────────
function animateCount(el, finalVal) {
  const raw = String(finalVal).replace(/[^0-9.%]/g, '').trim();
  const n = parseFloat(raw);
  if (!isFinite(n) || raw.includes('%')) {
    el.textContent = finalVal;
    return;
  }
  const suffix = String(finalVal).replace(/[0-9]/g, '');
  const dur = 900;
  const t0 = performance.now();
  const step = (now) => {
    const p = Math.min((now - t0) / dur, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(n * eased) + suffix;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
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
      animateCount(el, val);
    };
    const fv = (v, fb) => (v == null ? fb : v);
    set('statTotal',    fv(d.total, '—'));
    set('statCompleted', fv(d.completed, '—'));
    set('statFailed',   fv(d.failed, '—'));
    set('statPending',  fv(d.pending, '—'));
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
  if (browseBtn) browseBtn.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

  // ─── Drag & Drop ──────────────────────────────────────────────────────────
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) uploadFiles(Array.from(e.dataTransfer.files));
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) uploadFiles(Array.from(e.target.files));
  });

  // ─── Refresh Button ───────────────────────────────────────────────────────
  const refreshBtn = document.getElementById('refreshBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      refreshBtn.classList.add('spinning');
      Promise.all([loadGallery(), loadStats()]).finally(() => {
        setTimeout(() => refreshBtn.classList.remove('spinning'), 600);
      });
    });
  }

  // ─── Filter Buttons ────────────────────────────────────────────────────────
  function setFilter(name) {
    currentFilter = name;
    filterBtns.forEach(b => b.classList.toggle('active', b.dataset.filter === name));
  }
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => setFilter(btn.dataset.filter));
  });

  // ─── Drop Zone Reset ───────────────────────────────────────────────────────
  function resetDropZone() {
    const target = dropZoneContent || dropZone;
    target.innerHTML = `
      <span class="upload-icon" aria-hidden="true">📡</span>
      <p><strong>Drag vehicle image into scan zone</strong></p>
      <p class="subtitle">JPG · PNG · WEBP — 15MB</p>
      <button class="btn-upload" type="button" id="browseBtn">Browse Files</button>
    `;
    const bb = document.getElementById('browseBtn');
    if (bb) bb.addEventListener('click', () => fileInput.click());
  }

  // ─── Upload Logic (multi-file queue) ──────────────────────────────────────
  async function uploadFiles(files) {
    const list = Array.from(files).filter(f =>
      /^image\/(jpeg|png|webp)$/.test((f.type || '').toLowerCase()) ||
      /\.(jpe?g|png|webp)$/i.test(f.name || '')
    );
    if (!list.length) {
      showToast('No valid image files selected (JPG · PNG · WEBP)', 'error');
      return;
    }

    setFilter('all');

    const target = dropZoneContent || dropZone;
    target.innerHTML = `
      <span class="upload-icon">⏳</span>
      <p><strong>Uploading ${list.length} file${list.length > 1 ? 's' : ''} &amp; queuing analysis...</strong></p>
      <p class="subtitle">ENTERING SCAN QUEUE</p>
      <div class="upload-progress">
        <div class="progress-label">UPLOADING 0/${list.length}</div>
        <div class="progress-track"><div class="progress-fill"></div></div>
      </div>`;

    const progLabel = (target.getElementsByClassName('progress-label'))[0];
    const progFill = (target.getElementsByClassName('progress-fill'))[0];

    let okCount = 0, done = 0, firstId = null;
    for (const file of list) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch('/api/v1/images', { method: 'POST', body: formData });
        const data = await parseResponse(res);
        if (!res.ok) throw new Error(data.detail || 'Upload failed');
        okCount++;
        if (!firstId) firstId = data.id;
        showToast(`✔ "${file.name}" queued for analysis`, 'success');
      } catch (err) {
        console.error('Upload Error:', err.message);
        showToast(`"${file.name}": ${err.message}`, 'error');
      }
      done++;
      if (progLabel) progLabel.textContent = `UPLOADING ${done}/${list.length} — ${okCount} OK`;
      if (progFill) progFill.style.width = `${Math.round((done / list.length) * 100)}%`;
    }

    resetDropZone();
    if (fileInput) fileInput.value = '';
    loadGallery();
    loadStats();
    if (firstId) inspectImage(firstId);
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
      uploadFiles([file]);
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
          scoreTag = `<span class="score-badge score-low">❌ Failed</span>`;
        } else if (item.status === 'processing') {
          scoreTag = `<span class="score-badge score-medium">⚙️ Analyzing...</span>`;
        } else if (item.status === 'pending') {
          scoreTag = `<span class="score-badge score-medium">⏳ Pending</span>`;
        }

        const res_px = item.width && item.height ? `${item.width}×${item.height}` : '';

        let plateLine = '';
        if (item.status === 'completed' && item.plate_text) {
          const mark = item.plate_valid === false ? '?' : '✓';
          const cls = item.plate_valid === false ? 'p-no' : 'p-ok';
          plateLine = `<div class="plate-line"><span class="${cls}">${mark} ${item.plate_text}</span></div>`;
        } else if (item.status === 'completed') {
          plateLine = `<div class="plate-line"><span class="p-no">NO PLATE DETECTED</span></div>`;
        } else if (item.status === 'pending' || item.status === 'processing') {
          plateLine = `<div class="plate-line"><span class="p-wait">SCANNING PLATE...</span></div>`;
        }

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
            ${plateLine}
          </div>`;

        card.querySelector('.delete-btn').addEventListener('click', (e) => deleteImage(item.id, item.original_filename, e));
        card.addEventListener('click', () => inspectImage(item.id));
        gallery.appendChild(card);
      }

      // Auto refresh gallery if any images are still in pending/processing status
      const hasActive = data.items.some(i => i.status === 'pending' || i.status === 'processing');
      if (hasActive) {
        setTimeout(loadGallery, 3000);
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

      // Prominent License Plate text formatting
      const recognizedPlateText = plate.plate_text || (ocr.text ? ocr.text.trim() : null);
      const plateBadgeHtml = recognizedPlateText
        ? `<span class="plate-badge-highlight" style="display:inline-block; padding:2px 8px; border-radius:4px; background:#1e293b; color:#38bdf8; font-weight:700; font-family:monospace; letter-spacing:1px; border:1px solid #0284c7;">${recognizedPlateText}</span>`
        : '';

      const formatLabel = plate.format_type ? ` · <span style="font-size:0.75rem; opacity:0.8;">${plate.format_type}</span>` : '';

      const plateStatusHtml = plate.valid
        ? `🟢 Valid ${plateBadgeHtml}${formatLabel} (${plate.confidence ? Math.round(plate.confidence * 100) + '%' : '90%'})`
        : (plate.detected ? `🟡 Detected ${plateBadgeHtml}${formatLabel}` : '🔴 Not Detected');

      const ocrSceneTextDisplay = recognizedPlateText
        ? `${plateBadgeHtml} ${ocr.text && ocr.text !== recognizedPlateText ? `<span style="font-size:0.75rem; color:var(--text-muted);">(raw: ${ocr.text})</span>` : ''}`
        : (ocr.text || 'None detected');

      metricsContainer.innerHTML = `
        <div class="metric-item">
          <span>Clarity / Blur</span>
          <strong>${blur.is_blurry ? '🔴 Blurry' : '🟢 Sharp'} (${blur.score == null ? 0 : blur.score})</strong>
        </div>
        <div class="metric-item">
          <span>Brightness / Lighting</span>
          <strong style="text-transform:capitalize;">${bright.status || 'N/A'} (${bright.score == null ? 0 : bright.score}${contrastTxt})</strong>
        </div>
        <div class="metric-item">
          <span>License Plate</span>
          <strong>${plateStatusHtml}</strong>
        </div>
        <div class="metric-item">
          <span>OCR Scene Text</span>
          <strong>${ocrSceneTextDisplay}</strong>
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
        issuesContainer.innerHTML += `<div class="issue-chip issue-high" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
          <div>🔴 <strong>Processing Failed</strong>: ${data.error_message || 'Validation checks failed.'}</div>
          <button id="reanalyzeBtn" class="btn-upload" style="padding:0.3rem 0.8rem; font-size:0.85rem;">🔄 Re-analyze</button>
        </div>`;
      } else {
        issuesContainer.innerHTML += `<div style="text-align:right; margin-bottom:0.5rem;">
          <button id="reanalyzeBtn" class="btn-upload" style="padding:0.3rem 0.8rem; font-size:0.85rem; background:var(--bg-card); border:1px solid var(--border-glow);">🔄 Re-analyze Image</button>
        </div>`;
      }

      if (data.issues && data.issues.length > 0) {
        data.issues.forEach(issue => {
          const cls = issue.severity === 'high' ? 'issue-high' : issue.severity === 'medium' ? 'issue-medium' : 'issue-low';
          issuesContainer.innerHTML += `<div class="issue-chip ${cls}">
            ⚠️ <strong>${issue.type}</strong>: ${issue.description}</div>`;
        });
      } else if (data.status === 'completed') {
        issuesContainer.innerHTML += `<div class="issue-chip issue-low">🟢 No quality or authenticity issues detected.</div>`;
      }

      const reanalyzeBtn = document.getElementById('reanalyzeBtn');
      if (reanalyzeBtn) reanalyzeBtn.addEventListener('click', async () => {
        try {
          showToast('Re-triggering analysis pipeline...', 'info');
          const r = await fetch(`/api/v1/images/${imageId}/reanalyze`, { method: 'POST' });
          if (!r.ok) throw new Error('Failed to start re-analysis');
          showToast('Analysis restarted!', 'success');
          inspectImage(imageId);
          loadGallery();
          loadStats();
        } catch (e) {
          showToast(e.message, 'error');
        }
      });

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

// ═══════════════════════════════════════════════════════════════════════
// VFX MODULE — particle network, cursor glow, 3D tilt, live clocks
// ═══════════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ─── 1. Particle Neural Network ────────────────────────────────────────
  const canvas = document.getElementById('fxCanvas');
  if (canvas && !reduced) {
    const ctx = canvas.getContext('2d');
    let W, H, particles = [];
    const DPR = Math.min(window.devicePixelRatio || 1, 1.75);
    const mouse = { x: null, y: null };

    const COLORS = ['0,229,255', '255,180,43', '139,123,255'];

    function resize() {
      W = canvas.width = window.innerWidth * DPR;
      H = canvas.height = window.innerHeight * DPR;
      canvas.style.width = window.innerWidth + 'px';
      canvas.style.height = window.innerHeight + 'px';
      const count = Math.min(90, Math.floor((window.innerWidth * window.innerHeight) / 24000));
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: Math.random() * 1.6 + 0.6,
        c: COLORS[Math.floor(Math.random() * COLORS.length)]
      }));
    }

    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', (e) => {
      mouse.x = e.clientX * DPR;
      mouse.y = e.clientY * DPR;
    }, { passive: true });
    resize();

    const LINK_DIST = 165 * DPR;

    (function tick() {
      ctx.clearRect(0, 0, W, H);
      for (const p of particles) {
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
        if (mouse.x != null) {
          const dx = mouse.x - p.x, dy = mouse.y - p.y;
          const d = Math.hypot(dx, dy);
          if (d < 230 * DPR && d > 0.01) {
            p.vx += (dx / d) * 0.008;
            p.vy += (dy / d) * 0.008;
          }
          const cap = 0.55;
          p.vx = Math.max(-cap, Math.min(cap, p.vx));
          p.vy = Math.max(-cap, Math.min(cap, p.vy));
        }
        p.x += p.vx; p.y += p.vy;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * DPR, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.c},0.75)`;
        ctx.fill();
      }
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i], b = particles[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d = Math.hypot(dx, dy);
          if (d < LINK_DIST) {
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = `rgba(0,229,255,${(1 - d / LINK_DIST) * 0.14})`;
            ctx.lineWidth = 1 * DPR;
            ctx.stroke();
          }
        }
      }
      requestAnimationFrame(tick);
    })();
  } else if (canvas) {
    canvas.style.display = 'none';
  }

  // ─── 2. Cursor Glow ────────────────────────────────────────────────────
  const glow = document.getElementById('cursorGlow');
  const isTouch = window.matchMedia('(pointer: coarse)').matches;
  if (glow && !reduced && !isTouch) {
    let gx = -500, gy = -500, tx = -500, ty = -500;
    document.addEventListener('mousemove', (e) => { tx = e.clientX; ty = e.clientY; }, { passive: true });
    (function glowTick() {
      gx += (tx - gx) * 0.12;
      gy += (ty - gy) * 0.12;
      glow.style.transform = `translate(${gx}px, ${gy}px) translate(-50%, -50%)`;
      requestAnimationFrame(glowTick);
    })();
  } else if (glow) {
    glow.style.display = 'none';
  }

  // ─── 3. 3D Tilt Cards ──────────────────────────────────────────────────
  if (!reduced && !isTouch) {
    const tiltables = () => document.querySelectorAll('.image-card, .stat-card, .hud-card, .btn-sample');
    const applyTilt = (el, e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      const max = el.classList.contains('image-card') ? 6 : 3;
      el.style.transform = `perspective(700px) rotateX(${(-py * max).toFixed(2)}deg) rotateY(${(px * max).toFixed(2)}deg) translateY(-2px)`;
    };
    const resetTilt = (el) => { el.style.transform = ''; };

    document.addEventListener('mousemove', (e) => {
      if (!e.target.closest) return;
      const el = e.target.closest('.image-card, .stat-card, .hud-card, .btn-sample');
      if (el) applyTilt(el, e);
    }, { passive: true });

    document.addEventListener('mouseout', (e) => {
      if (!e.target.closest) return;
      const el = e.target.closest('.image-card, .stat-card, .hud-card, .btn-sample');
      if (el) resetTilt(el);
    }, { passive: true });
  }

  // ─── 4. Live System Clock ──────────────────────────────────────────────
  function tickClocks() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    const date = `${now.getFullYear()}/${pad(now.getMonth() + 1)}/${pad(now.getDate())}`;
    const el = document.getElementById('sysClock');
    if (el) {
      el.querySelector('.t').textContent = time;
      el.querySelector('.d').textContent = date;
    }
    const fc = document.getElementById('footerClock');
    if (fc) {
      fc.textContent = `${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())}`;
    }
  }
  tickClocks();
  setInterval(tickClocks, 1000);
});
