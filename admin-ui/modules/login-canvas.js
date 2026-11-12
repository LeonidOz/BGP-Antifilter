// Animated network canvas and its login screen labels.
import { $ } from "./dom.js";

const canvasState = {
  loginCanvasStarted: false,
  loginNetworkLabels: [],
};

function loginCanvasSubnets() {
  const fallback = ["192.168.77.111", "192.168.55.1", "172.21.0.2", "127.0.0.1"];
  const labels = [];
  const seen = new Set();
  for (const label of (canvasState.loginNetworkLabels.length ? canvasState.loginNetworkLabels : fallback).filter(Boolean)) {
    const raw = String(label).trim();
    const match = raw.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}$/);
    const text = match ? `${match[1]}.0/24` : raw;
    if (seen.has(text)) {
      continue;
    }
    seen.add(text);
    labels.push({
      raw,
      text,
    });
    if (labels.length >= 4) {
      break;
    }
  }
  const layout = [
    {x: .2, y: .28, count: 5},
    {x: .78, y: .26, count: 5},
    {x: .72, y: .76, count: 4},
    {x: .26, y: .72, count: 4},
  ];
  return layout.map((item, index) => ({
    ...item,
    label: labels[index]?.text || labels[index]?.raw || "LAN"
  }));
}

function startLoginNetworkCanvas() {
  if (canvasState.loginCanvasStarted) return;
  const canvas = $("login-network-canvas");
  if (!canvas) return;
  canvasState.loginCanvasStarted = true;

  const ctx = canvas.getContext("2d");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let width = 0;
  let height = 0;
  let dpr = 1;
  let frame = 0;
  let animationId = null;
  let nodes = [];
  let packets = [];
  const pointer = {x: 0, y: 0, active: false};
  const hubTarget = {x: 0, y: 0};

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = Math.max(1, Math.floor(width * dpr));
    canvas.height = Math.max(1, Math.floor(height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    createTopology();
  }

  function createTopology() {
    const subnets = loginCanvasSubnets();
    const centerX = width * .5;
    const centerY = height * .5;
    pointer.x = pointer.x || centerX;
    pointer.y = pointer.y || centerY;
    hubTarget.x = centerX;
    hubTarget.y = centerY;
    nodes = [{x: centerX, y: centerY, baseX: centerX, baseY: centerY, r: 13, label: "", hub: true, pulse: Math.random() * 10}];
    for (const subnet of subnets) {
      const gatewayX = width * subnet.x;
      const gatewayY = height * subnet.y;
      nodes.push({x: gatewayX, y: gatewayY, baseX: gatewayX, baseY: gatewayY, r: 10, label: subnet.label, gateway: true, pulse: Math.random() * 10});
      for (let i = 0; i < subnet.count; i += 1) {
        const angle = (Math.PI * 2 * i) / subnet.count + .32;
        const radius = 54 + (i % 2) * 26;
        const nodeX = width * subnet.x + Math.cos(angle) * radius;
        const nodeY = height * subnet.y + Math.sin(angle) * radius;
        nodes.push({
          x: nodeX,
          y: nodeY,
          baseX: nodeX,
          baseY: nodeY,
          r: 4 + (i % 3),
          label: "",
          gateway: false,
          pulse: Math.random() * 10
        });
      }
    }
    packets = Array.from({length: Math.max(8, Math.floor(width / 120))}, (_, index) => ({
      from: 0,
      to: 1 + (index % (nodes.length - 1)),
      progress: Math.random(),
      speed: .0028 + Math.random() * .0032,
      color: index % 3 === 0 ? "#55d987" : index % 3 === 1 ? "#3dd6ff" : "#f3bd4d"
    }));
  }

  function setPointer(clientX, clientY, active = true) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = clientX - rect.left;
    pointer.y = clientY - rect.top;
    pointer.active = active;
  }

  function releasePointer() {
    pointer.active = false;
  }

  function updateTopology() {
    const hub = nodes[0];
    const targetX = pointer.active ? pointer.x : width * .5;
    const targetY = pointer.active ? pointer.y : height * .5;
    const maxRadius = Math.min(width, height) * .22;
    const dx = targetX - width * .5;
    const dy = targetY - height * .5;
    const distance = Math.hypot(dx, dy) || 1;
    const scale = Math.min(distance, maxRadius) / distance;
    hubTarget.x = width * .5 + dx * scale;
    hubTarget.y = height * .5 + dy * scale;
    hub.x += (hubTarget.x - hub.x) * .075;
    hub.y += (hubTarget.y - hub.y) * .075;

    nodes.slice(1).forEach((node, index) => {
      const wave = Math.sin(frame * .018 + node.pulse) * (node.gateway ? 4 : 7);
      const pullX = (hub.x - width * .5) * (node.gateway ? -.035 : -.055);
      const pullY = (hub.y - height * .5) * (node.gateway ? -.035 : -.055);
      const angle = Math.atan2(node.baseY - hub.y, node.baseX - hub.x);
      node.x += (node.baseX + Math.cos(angle) * wave + pullX - node.x) * .045;
      node.y += (node.baseY + Math.sin(angle) * wave + pullY - node.y) * .045;
      if (pointer.active && index % 5 === 0) {
        const pdx = node.x - pointer.x;
        const pdy = node.y - pointer.y;
        const pd = Math.hypot(pdx, pdy) || 1;
        if (pd < 150) {
          node.x += (pdx / pd) * (150 - pd) * .012;
          node.y += (pdy / pd) * (150 - pd) * .012;
        }
      }
    });
  }

  function line(from, to, alpha = .25) {
    ctx.strokeStyle = `rgba(61, 214, 255, ${alpha})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    const midX = (from.x + to.x) / 2;
    const midY = (from.y + to.y) / 2;
    ctx.quadraticCurveTo(midX, midY - 24, to.x, to.y);
    ctx.stroke();
  }

  function draw() {
    frame += 1;
    updateTopology();
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "rgba(7, 16, 23, .76)";
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = "rgba(61, 214, 255, .055)";
    ctx.lineWidth = 1;
    for (let x = (frame * .18) % 34; x < width; x += 34) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = (frame * .12) % 34; y < height; y += 34) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const hub = nodes[0];
    nodes.slice(1).forEach((node, index) => {
      if (node.gateway || index % 3 === 0) line(hub, node, node.gateway ? .28 : .1);
    });
    for (let i = 1; i < nodes.length - 1; i += 1) {
      if (i % 4 === 0) line(nodes[i], nodes[i + 1], .1);
    }

    packets.forEach(packet => {
      const from = nodes[packet.from];
      const to = nodes[packet.to];
      packet.progress += packet.speed * (reduceMotion ? .35 : 1);
      if (packet.progress > 1) {
        packet.progress = 0;
        packet.to = 1 + Math.floor(Math.random() * (nodes.length - 1));
      }
      const x = from.x + (to.x - from.x) * packet.progress;
      const y = from.y + (to.y - from.y) * packet.progress - Math.sin(packet.progress * Math.PI) * 18;
      ctx.fillStyle = packet.color;
      ctx.shadowColor = packet.color;
      ctx.shadowBlur = 16;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    nodes.forEach(node => {
      const pulse = .5 + Math.sin(frame * .035 + node.pulse) * .5;
      ctx.fillStyle = node.hub ? "#dffaff" : node.gateway ? "#55d987" : "#3dd6ff";
      ctx.shadowColor = node.gateway ? "#55d987" : "#3dd6ff";
      ctx.shadowBlur = node.hub ? 26 : 13;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r + pulse * (node.hub ? 3 : 1.4), 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      if (node.label) {
        ctx.font = node.hub ? "700 13px Inter, Segoe UI, sans-serif" : "600 11px Inter, Segoe UI, sans-serif";
        ctx.fillStyle = node.hub ? "#e5f2ff" : "rgba(229, 242, 255, .68)";
        ctx.fillText(node.label, node.x + 15, node.y - 11);
      }
    });

    animationId = requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  window.addEventListener("pointermove", event => setPointer(event.clientX, event.clientY));
  window.addEventListener("pointerleave", releasePointer);
  window.addEventListener("blur", releasePointer);
  resize();
  draw();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    } else if (!document.hidden && !animationId) {
      animationId = requestAnimationFrame(draw);
    }
  });
}

export { canvasState, loginCanvasSubnets, startLoginNetworkCanvas };
