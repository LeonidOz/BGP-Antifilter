export default async function teardown() {
  await fetch("http://127.0.0.1:18761/__test/stop", {method: "POST"}).catch(() => {});
}
