/* landing.js — animations, terminal, scroll reveals */
'use strict';

(function () {

  /* ─── Terminal typing animation ─── */
  var termEl = document.getElementById('terminal-content');
  if (termEl) {
    var SEQ = [
      { type: 'prompt' },
      { type: 'type',  text: 'docker compose up -d', speed: 58 },
      { type: 'newline' },
      { type: 'pause', ms: 480 },
      { type: 'line',  text: '[+] Running 3/3',                              cls: 't-dim' },
      { type: 'line',  text: ' ✔ codesentinel_ollama   Started  0.7s', cls: 't-success' },
      { type: 'line',  text: ' ✔ codesentinel_app      Started  1.1s', cls: 't-success' },
      { type: 'line',  text: ' ✔ codesentinel_caddy    Started  0.4s', cls: 't-success' },
      { type: 'pause', ms: 1100 },
      { type: 'blank' },
      { type: 'line',  text: '[webhook] PR #47 → "Add payment endpoint"', cls: 't-info' },
      { type: 'pause', ms: 340 },
      { type: 'line',  text: '[review]  Analyzing 3 changed files...',         cls: 't-info' },
      { type: 'pause', ms: 720 },
      { type: 'blank' },
      { type: 'parts', parts: [
        { text: '         api/payments.py', cls: 't-path' },
        { text: ':34  ', cls: 't-dim' },
        { text: 'SECURITY', cls: 't-warn' },
      ]},
      { type: 'parts', parts: [
        { text: '         ⚠ ', cls: 't-warn' },
        { text: 'SQL query uses string interpolation', cls: '' },
      ]},
      { type: 'line',  text: '           → Use parameterized queries', cls: 't-dim' },
      { type: 'pause', ms: 360 },
      { type: 'parts', parts: [
        { text: '         api/payments.py', cls: 't-path' },
        { text: ':89  ', cls: 't-dim' },
        { text: 'SECURITY', cls: 't-warn' },
      ]},
      { type: 'parts', parts: [
        { text: '         ⚠ ', cls: 't-warn' },
        { text: 'Secret key logged to stdout', cls: '' },
      ]},
      { type: 'line',  text: '           → Use env vars or a secrets manager', cls: 't-dim' },
      { type: 'pause', ms: 600 },
      { type: 'blank' },
      { type: 'parts', parts: [
        { text: '[review]  ', cls: 't-info' },
        { text: '✓ ', cls: 't-success' },
        { text: '2 comments posted to GitHub PR #47', cls: '' },
      ]},
      { type: 'parts', parts: [
        { text: '[review]  ', cls: 't-info' },
        { text: '✓ ', cls: 't-success' },
        { text: 'Done in 3.8s · code stayed local', cls: '' },
      ]},
    ];

    var cursor = document.createElement('span');
    cursor.className = 't-cursor';
    cursor.setAttribute('aria-hidden', 'true');

    var idx = 0;

    function mkSpan(cls, text) {
      if (!cls) return document.createTextNode(text);
      var s = document.createElement('span');
      s.className = cls;
      s.textContent = text;
      return s;
    }

    function appendLine(node) {
      termEl.appendChild(node);
      termEl.appendChild(document.createTextNode('\n'));
    }

    function typeText(text, speed, done) {
      var i = 0;
      var s = document.createElement('span');
      s.className = 't-cmd';
      termEl.appendChild(s);
      if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
      s.appendChild(cursor);

      function tick() {
        if (i < text.length) {
          cursor.insertAdjacentText('beforebegin', text[i++]);
          setTimeout(tick, speed + (Math.random() * 20 - 10));
        } else {
          done();
        }
      }
      tick();
    }

    function next() {
      if (idx >= SEQ.length) {
        setTimeout(function () {
          termEl.textContent = '';
          idx = 0;
          next();
        }, 4200);
        return;
      }

      var step = SEQ[idx++];

      if (step.type === 'pause') {
        setTimeout(next, step.ms);
        return;
      }

      if (step.type === 'prompt') {
        var p = document.createElement('span');
        p.className = 't-prompt';
        p.textContent = '❯ ';
        termEl.appendChild(p);
        if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
        termEl.appendChild(cursor);
        next();
        return;
      }

      if (step.type === 'type') {
        if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
        typeText(step.text, step.speed, function () {
          termEl.appendChild(document.createTextNode('\n'));
          next();
        });
        return;
      }

      if (step.type === 'newline') {
        termEl.appendChild(document.createTextNode('\n'));
        next();
        return;
      }

      if (step.type === 'blank') {
        termEl.appendChild(document.createTextNode('\n'));
        setTimeout(next, 80);
        return;
      }

      if (step.type === 'line') {
        appendLine(mkSpan(step.cls, step.text));
        setTimeout(next, 90);
        return;
      }

      if (step.type === 'parts') {
        var frag = document.createDocumentFragment();
        step.parts.forEach(function (pt) { frag.appendChild(mkSpan(pt.cls, pt.text)); });
        termEl.appendChild(frag);
        termEl.appendChild(document.createTextNode('\n'));
        setTimeout(next, 90);
        return;
      }

      next();
    }

    setTimeout(next, 900);
  }

  /* ─── Feature card mouse-tracked glow ─── */
  document.querySelectorAll('.feature-card').forEach(function (card) {
    card.addEventListener('mousemove', function (e) {
      var r = card.getBoundingClientRect();
      card.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100) + '%');
      card.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100) + '%');
    });
  });

  /* ─── Scroll reveal ─── */
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });

    document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('visible'); });
  }

  /* ─── Copy code button ─── */
  var copyBtn = document.getElementById('copy-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      var codeEl = document.getElementById('qs-code');
      if (!codeEl) return;
      navigator.clipboard.writeText(codeEl.textContent).then(function () {
        var label = copyBtn.querySelector('.copy-label');
        if (label) {
          var orig = label.textContent;
          label.textContent = 'Copied!';
          setTimeout(function () { label.textContent = orig; }, 2000);
        }
      }).catch(function () {});
    });
  }

})();
