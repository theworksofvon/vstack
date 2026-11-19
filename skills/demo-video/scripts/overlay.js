// Demo overlay: a drawn cursor, click ripples, a caption, a highlight ring and
// a notice. Lives outside the app's React tree and takes no pointer events.
(() => {
  if (window.__demo) return;
  const ACCENT = "#f5b301";
  const store = (key, value) => {
    try {
      if (value === undefined) return JSON.parse(sessionStorage.getItem(key));
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      return null;
    }
  };

  const css = `
    #__demo { position: fixed; inset: 0; pointer-events: none; z-index: 2147483647;
      font-family: "Semplicita Pro", "Inter", system-ui, sans-serif; }
    #__demo * { box-sizing: border-box; }
    #__demo .cursor { position: absolute; left: 0; top: 0; width: 30px; height: 30px;
      transform: translate(-100px, -100px);
      filter: drop-shadow(0 3px 5px rgba(0,0,0,.35)); will-change: transform; }
    #__demo .ripple { position: absolute; width: 16px; height: 16px; margin: -8px 0 0 -8px;
      border-radius: 50%; border: 3px solid ${ACCENT}; background: rgba(245,179,1,.25);
      animation: demo-ripple 520ms ease-out forwards; }
    @keyframes demo-ripple { to { transform: scale(4.2); opacity: 0; } }
    #__demo .ring { position: absolute; border: 3px solid ${ACCENT}; border-radius: 10px;
      box-shadow: 0 0 0 6px rgba(245,179,1,.22), 0 0 28px rgba(245,179,1,.45);
      opacity: 0; transition: opacity 280ms ease, transform 280ms ease; transform: scale(1.06); }
    #__demo .ring.on { opacity: 1; transform: scale(1); }
    #__demo .ring .tag { position: absolute; left: -3px; bottom: calc(100% + 8px); white-space: nowrap;
      background: ${ACCENT}; color: #1a1300; font-weight: 700; font-size: 15px; padding: 5px 11px;
      border-radius: 7px; }
    #__demo .ring .tag.below { bottom: auto; top: calc(100% + 8px); }
    #__demo .caption { position: absolute; left: 50%; bottom: 26px; transform: translate(-50%, 24px);
      display: flex; align-items: center; gap: 14px; padding: 12px 22px 12px 12px;
      background: rgba(11,18,32,.94); color: #fff; border-radius: 999px; opacity: 0;
      box-shadow: 0 12px 34px rgba(0,0,0,.35); transition: opacity 320ms ease, transform 320ms ease; }
    #__demo .caption.on { opacity: 1; transform: translate(-50%, 0); }
    #__demo .caption .step { background: ${ACCENT}; color: #1a1300; font-weight: 800; font-size: 15px;
      border-radius: 999px; padding: 6px 13px; letter-spacing: .04em; }
    #__demo .caption .text { font-size: 20px; font-weight: 600; letter-spacing: .01em; }
    #__demo .notice { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -40%);
      background: rgba(11,18,32,.95); color: #fff; padding: 22px 34px; border-radius: 16px;
      font-size: 22px; font-weight: 600; text-align: center; opacity: 0; max-width: 620px;
      box-shadow: 0 18px 50px rgba(0,0,0,.4); transition: opacity 300ms ease, transform 300ms ease; }
    #__demo .notice small { display: block; margin-top: 8px; font-size: 16px; font-weight: 500;
      color: #c6cfde; }
    #__demo .notice.on { opacity: 1; transform: translate(-50%, -50%); }
    #__demo .speed { position: absolute; right: 24px; top: 20px; background: ${ACCENT}; color: #1a1300;
      font-weight: 800; font-size: 17px; padding: 8px 15px; border-radius: 999px; opacity: 0;
      transition: opacity 200ms ease; }
    #__demo .speed.on { opacity: 1; }
    #__demo .tick { position: absolute; left: 0; top: 0; width: 2px; height: 2px; }
  `;

  const root = document.createElement("div");
  root.id = "__demo";
  root.innerHTML = `<style>${css}</style>
    <div class="caption"><span class="step"></span><span class="text"></span></div>
    <div class="notice"></div>
    <div class="speed"></div>
    <div class="tick"></div>
    <svg class="cursor" viewBox="0 0 30 30"><path d="M4 2 L4 24 L10 18.5 L14 27.5 L18 25.7 L14 17 L22 17 Z"
      fill="#fff" stroke="#0b1220" stroke-width="2" stroke-linejoin="round"/></svg>`;
  const mount = () => {
    const html = document.documentElement;
    if (html && root.parentNode !== html) html.appendChild(root);
  };
  const watch = () => {
    mount();
    new MutationObserver(mount).observe(document.documentElement, {
      childList: true,
    });
  };
  if (document.documentElement) watch();
  else document.addEventListener("readystatechange", watch, { once: true });

  const cursor = root.querySelector(".cursor");
  const caption = root.querySelector(".caption");
  const notice = root.querySelector(".notice");
  const speed = root.querySelector(".speed");
  const tick = root.querySelector(".tick");
  let flip = false;
  let here = [-100, -100];
  let glide = 0;

  // A hand does not move on a straight line at an even speed: the cursor
  // follows a critically damped spring along a slight arc, and still lands on
  // the target at `ms`, because the recorder clicks there right after.
  const place = ([x, y]) => {
    here = [x, y];
    cursor.style.transform = `translate(${x - 4}px, ${y - 2}px)`;
  };
  const spring = (p) => 1 - (1 + 5 * p) * Math.exp(-5 * p);
  const arc = 0.08; // the bend, as a part of the distance

  const demo = {
    move(x, y, ms = 600) {
      cancelAnimationFrame(glide);
      store("demo-cursor", [x, y]);
      const [x0, y0] = here;
      const dx = x - x0;
      const dy = y - y0;
      if (ms <= 0) return place([x, y]);
      const start = performance.now();
      const frame = (now) => {
        const p = Math.min((now - start) / ms, 1);
        const s = spring(p) / spring(1);
        const bend = Math.sin(Math.PI * s) * arc;
        place([x0 + dx * s - dy * bend, y0 + dy * s + dx * bend]);
        if (p < 1) glide = requestAnimationFrame(frame);
      };
      glide = requestAnimationFrame(frame);
    },
    ripple(x, y) {
      const dot = document.createElement("div");
      dot.className = "ripple";
      dot.style.left = `${x}px`;
      dot.style.top = `${y}px`;
      root.appendChild(dot);
      setTimeout(() => dot.remove(), 600);
    },
    caption(step, text) {
      if (!text) {
        caption.classList.remove("on");
        store("demo-caption", null);
        return;
      }
      caption.querySelector(".step").textContent = step;
      caption.querySelector(".text").textContent = text;
      caption.classList.add("on");
      store("demo-caption", [step, text]);
    },
    ring(rect, label, below) {
      const ring = document.createElement("div");
      ring.className = "ring";
      const pad = 6;
      ring.style.left = `${rect.x - pad}px`;
      ring.style.top = `${rect.y - pad}px`;
      ring.style.width = `${rect.width + pad * 2}px`;
      ring.style.height = `${rect.height + pad * 2}px`;
      if (label) {
        const tag = document.createElement("span");
        tag.className = below ? "tag below" : "tag";
        tag.textContent = label;
        ring.appendChild(tag);
      }
      root.appendChild(ring);
      requestAnimationFrame(() => ring.classList.add("on"));
      return ring;
    },
    clearRings() {
      for (const ring of root.querySelectorAll(".ring")) {
        ring.classList.remove("on");
        setTimeout(() => ring.remove(), 320);
      }
    },
    notice(title, detail) {
      if (!title) {
        notice.classList.remove("on");
        return;
      }
      notice.innerHTML = "";
      notice.append(title);
      if (detail) {
        const small = document.createElement("small");
        small.textContent = detail;
        notice.appendChild(small);
      }
      notice.classList.add("on");
    },
    speed(text) {
      speed.textContent = text || "";
      speed.classList.toggle("on", Boolean(text));
    },
    tick() {
      flip = !flip;
      tick.style.background = flip ? "rgba(0,0,0,.02)" : "rgba(0,0,0,.03)";
    },
    // The screen path, for a browser tool: the cursor glides to the element
    // like a hand, then clicks it when it lands, so the video shows the move
    // before the page changes. `target` is a CSS selector or an element.
    async click(target, ms = 700) {
      const [el, x, y] = await demo.point(target, ms);
      demo.ripple(x, y);
      synthetic = true;
      try {
        const at = {
          bubbles: true,
          cancelable: true,
          composed: true,
          view: window,
        };
        Object.assign(at, { clientX: x, clientY: y, button: 0 });
        const pointer = {
          ...at,
          pointerId: 1,
          isPrimary: true,
          pointerType: "mouse",
        };
        el.dispatchEvent(new PointerEvent("pointerdown", pointer));
        el.dispatchEvent(new MouseEvent("mousedown", at));
        el.focus?.({ preventScroll: true });
        el.dispatchEvent(new PointerEvent("pointerup", pointer));
        el.dispatchEvent(new MouseEvent("mouseup", at));
        el.dispatchEvent(new MouseEvent("click", { ...at, detail: 1 }));
      } finally {
        synthetic = false;
      }
      return `clicked at ${Math.round(x)},${Math.round(y)}`;
    },
    // Glides to the element and waits until the cursor is there: use it
    // before a click the page needs from the real browser tool (a file
    // picker, a drag), or to show a hover.
    async point(target, ms = 700) {
      const el =
        typeof target === "string" ? document.querySelector(target) : target;
      if (!el) throw new Error(`no element for ${target}`);
      el.scrollIntoView({ block: "nearest", inline: "nearest" });
      const box = el.getBoundingClientRect();
      const [x, y] = [box.x + box.width / 2, box.y + box.height / 2];
      if (Math.hypot(x - here[0], y - here[1]) > 4) {
        demo.move(x, y, ms);
        await new Promise((done) => setTimeout(done, ms + 60));
      }
      el.dispatchEvent(
        new PointerEvent("pointerover", {
          bubbles: true,
          clientX: x,
          clientY: y,
        }),
      );
      return [el, x, y];
    },
    follow() {
      if (following) return;
      following = true;
      if (here[0] < 0) place([innerWidth / 2, innerHeight / 2]);
      addEventListener(
        "pointermove",
        (e) => synthetic || demo.move(e.clientX, e.clientY, 220),
        true,
      );
      addEventListener(
        "pointerdown",
        (e) => {
          const [x, y] = [e.clientX, e.clientY];
          if (synthetic) return;
          // After `point`, the cursor is there already: only the ripple.
          const near = Math.hypot(x - here[0], y - here[1]) < 4;
          if (!near) demo.move(x, y, 260);
          setTimeout(() => demo.ripple(x, y), near ? 0 : 260);
        },
        true,
      );
      addEventListener(
        "focusin",
        (e) => {
          // Keyboard focus (Tab, or a tool that types into a field) with no
          // pointer event: the cursor goes to the field that gets the text.
          if (synthetic) return;
          const box = e.target.getBoundingClientRect?.();
          if (!box || !box.width) return;
          const [x, y] = [
            box.x + Math.min(box.width / 2, 40),
            box.y + box.height / 2,
          ];
          if (Math.hypot(x - here[0], y - here[1]) > box.width)
            demo.move(x, y, 400);
        },
        true,
      );
    },
  };
  let following = false;
  let synthetic = false;
  window.__demo = demo;

  const at = store("demo-cursor");
  if (at) place(at);
  const shown = store("demo-caption");
  if (shown) demo.caption(shown[0], shown[1]);
})();
