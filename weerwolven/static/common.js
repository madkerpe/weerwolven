// Gedeelde hulpjes: websocket met herverbinding, escaping, toasts.
window.WW = (function () {
  function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  let toastTimer = null;
  function toast(text, ms) {
    let el = document.getElementById('toast');
    if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; document.body.appendChild(el); }
    el.textContent = text; el.style.display = 'block';
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.style.display = 'none'; }, ms || 3500);
  }
  function connect(helloFn, handlers) {
    let ws = null, backoff = 500, closedByUs = false, queue = [];
    function open() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => {
        backoff = 500;
        ws.send(JSON.stringify({ type: 'hello', ...helloFn() }));
        while (queue.length) ws.send(queue.shift());
        handlers.onOpen && handlers.onOpen();
      };
      ws.onmessage = (e) => {
        let msg; try { msg = JSON.parse(e.data); } catch { return; }
        if (msg.type === 'state') handlers.onState && handlers.onState(msg.view);
        else if (msg.type === 'error') { if (handlers.onError) handlers.onError(msg); else toast(msg.text); }
        else handlers.onMessage && handlers.onMessage(msg);
      };
      ws.onclose = () => {
        handlers.onClose && handlers.onClose();
        if (closedByUs) return;
        setTimeout(open, backoff); backoff = Math.min(backoff * 1.7, 6000);
      };
      ws.onerror = () => { try { ws.close(); } catch {} };
    }
    open();
    return {
      send(obj) { const s = JSON.stringify(obj); if (ws && ws.readyState === 1) ws.send(s); else queue.push(s); },
      close() { closedByUs = true; ws && ws.close(); },
    };
  }
  const PHASE_NL = {
    lobby: 'Wachtkamer', reveal: 'Rollen lezen', night_cupido: 'Nacht', night_wolves: 'Nacht', night_witch: 'Nacht',
    hunter: 'De jager', day: 'Dag', vote: 'Stemming', dusk: 'Avond', end: 'Einde',
  };
  const ROLE_NL = { weerwolf: 'Weerwolf', burger: 'Burger', ziener: 'Ziener', heks: 'Heks', jager: 'Jager', cupido: 'Cupido' };
  function phaseLabel(v) {
    const p = PHASE_NL[v.phase] || v.phase;
    return v.day && v.phase !== 'lobby' && v.phase !== 'reveal' ? `${p} ${v.day}` : p;
  }
  function isNight(v) { return /^night_/.test(v.phase); }
  return { esc, toast, connect, phaseLabel, isNight, ROLE_NL, PHASE_NL };
})();
