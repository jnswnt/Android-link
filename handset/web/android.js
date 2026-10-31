'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const token = document.querySelector('meta[name="android-link-token"]').content;
  let state = {running: false, devices: [], adb: false, scrcpy: false};
  let busy = false;
  let failed = false;
  const audio = () => document.querySelector('input[name="audio"]:checked').value;
  const settings = () => ({audio: audio(), quality: $('quality').value, screenOff: $('screen-off').checked});
  const feedback = (text, error = false) => { $('feedback').textContent = text; $('feedback').dataset.error = String(error); };
  try {
    const saved = JSON.parse(localStorage.getItem('android-link-preferences') || '{}');
    document.documentElement.dataset.theme = saved.theme === 'light' ? 'light' : 'dark';
    if (['phone', 'pc', 'both'].includes(saved.audio)) document.querySelector(`input[name="audio"][value="${saved.audio}"]`).checked = true;
    if (['light', 'balanced', 'sharp'].includes(saved.quality)) $('quality').value = saved.quality;
    $('screen-off').checked = saved.screenOff === true;
  } catch (_) { /* Private browsing or invalid preferences: use safe defaults. */ }
  function save() {
    try { localStorage.setItem('android-link-preferences', JSON.stringify({...settings(), theme: document.documentElement.dataset.theme})); }
    catch (_) { feedback('Pengaturan tidak dapat disimpan; pilihan tetap berlaku untuk sesi ini.'); }
    render();
  }
  async function request(path, data) {
    const response = await fetch(`/api/android/${path}`, {signal: AbortSignal.timeout(45000), ...(data === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-Android-Link-Token': token}, body: JSON.stringify(data)
    })});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Permintaan gagal.');
    return result;
  }
  function render() {
    const ready = state.devices.some(d => d.serial === $('device').value && d.state === 'device');
    $('start').disabled = busy || failed || !ready || !state.adb || !state.scrcpy || state.running;
    $('stop').disabled = busy || failed || !state.running;
    $('apply').disabled = busy || failed || !state.running || !ready;
    $('device').disabled = busy || state.running;
    $('refresh').disabled = busy;
    document.querySelectorAll('[data-action]').forEach(button => { button.disabled = busy || failed || !state.running; });
    $('session-title').textContent = failed ? 'Koneksi aplikasi terputus' : state.running ? 'Sesi scrcpy berjalan' : 'Siap untuk terhubung';
    $('session-description').textContent = failed ? 'Refresh untuk memeriksa koneksi. Status perangkat belum diketahui.' : state.running ? 'Gunakan jendela scrcpy untuk melihat dan menyentuh layar HP.' : 'Sambungkan HP melalui USB dan izinkan USB debugging.';
    $('session-badge').textContent = failed ? 'Status tidak diketahui' : state.running ? `Perangkat: ${state.serial}` : 'Belum ada sesi';
    $('session-badge').dataset.running = String(!failed && state.running);
    const changed = state.settings && Object.entries(settings()).some(([key, value]) => state.settings[key] !== value);
    const names = {phone: 'HP saja', pc: 'PC saja', both: 'HP + PC'};
    $('pending').textContent = failed ? 'Koneksi terputus; status penerapan tidak diketahui.' : state.running
      ? `Tujuan audio sesi: ${names[state.settings.audio]}.${changed ? ' Ada perubahan; klik Terapkan untuk mulai ulang.' : ' Pilihan sudah dikirim ke scrcpy.'}`
      : 'Pilihan tersimpan di PC ini; belum diterapkan ke HP.';
  }
  async function refresh() {
    const previous = $('device').value;
    try {
      state = await request('status'); failed = false;
      const options = state.devices.map(d => { const option = document.createElement('option'); option.value = d.serial; option.textContent = `${d.name} · ${d.state}`; return option; });
      if (!options.length) { const option = document.createElement('option'); option.value = ''; option.textContent = 'Belum ada perangkat'; options.push(option); }
      $('device').replaceChildren(...options);
      const preferred = state.running ? state.serial : previous;
      if (state.devices.some(d => d.serial === preferred)) $('device').value = preferred;
      else { const ready = state.devices.find(d => d.state === 'device'); if (ready) $('device').value = ready.serial; }
      $('dependencies').textContent = `${state.adb ? '✓' : '✕'} ADB  ·  ${state.scrcpy ? '✓' : '✕'} scrcpy${state.error ? ` · ${state.error}` : ''}`;
      if (state.diagnostic) feedback(state.diagnostic, true);
    } catch (error) { failed = true; feedback(`Tidak dapat membaca status: ${error.message}`, true); }
    render();
  }
  async function perform(path, data) {
    if (busy) return;
    busy = true; render();
    try { const result = await request(path, data); feedback(result.message); }
    catch (error) { feedback(error.message, true); }
    finally { await refresh(); busy = false; render(); }
  }
  $('start').addEventListener('click', () => perform('start', {serial: $('device').value, ...settings()}));
  $('apply').addEventListener('click', () => perform('start', {serial: $('device').value, ...settings()}));
  $('stop').addEventListener('click', () => perform('stop', {}));
  $('refresh').addEventListener('click', () => { if (!busy) refresh(); });
  $('device').addEventListener('change', render);
  document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => perform('action', {action: button.dataset.action})));
  document.querySelectorAll('input[name="audio"], #quality, #screen-off').forEach(input => input.addEventListener('change', save));
  $('theme').addEventListener('click', () => { document.documentElement.dataset.theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'; save(); });
  $('settings-toggle').addEventListener('click', () => { const hidden = !$('android-settings').hidden; $('android-settings').hidden = hidden; $('settings-toggle').setAttribute('aria-expanded', String(!hidden)); });
  async function poll() { if (!busy) await refresh(); setTimeout(poll, 3000); }
  poll();
})();
