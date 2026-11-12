// Visibility of the login/admin screens and displayed version.
import { $ } from "./dom.js";
import { startLoginNetworkCanvas } from "./login-canvas.js";

function showLogin() {
  $("app-shell").classList.add("login-mode");
  $("sidebar").classList.add("hidden");
  $("login-view").classList.remove("hidden");
  $("admin-view").classList.add("hidden");
  startLoginNetworkCanvas();
}

function showAdmin() {
  $("app-shell").classList.remove("login-mode");
  $("sidebar").classList.remove("hidden");
  $("login-view").classList.add("hidden");
  $("admin-view").classList.remove("hidden");
}

function setVersion(version) {
  const value = version ? `v${version}` : "v-";
  $("version").textContent = value;
  $("login-footer-version").textContent = value;
  $("admin-footer-version").textContent = value;
}

export { setVersion, showAdmin, showLogin };
