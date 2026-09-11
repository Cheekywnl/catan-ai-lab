import { loadPyodide } from "./runtime/pyodide.mjs";
let ready;
let queue = Promise.resolve();
async function initialize() {
  self.postMessage({ status: "Loading the Python engine…" });
  const py = await loadPyodide({
    indexURL: new URL("./runtime/", self.location.href).href,
  });
  self.postMessage({ status: "Loading game rules and card tracking…" });
  const response = await fetch(
    new URL("./engine-source.zip", self.location.href),
  );
  if (!response.ok) throw new Error("The engine source could not be loaded.");
  py.unpackArchive(await response.arrayBuffer(), "zip", {
    extractDir: "/home/pyodide",
  });
  py.runPython("from engine.session import dispatch");
  return py;
}
self.onmessage = (event) => {
  const { id, ...request } = event.data;
  queue = queue.then(async () => {
    try {
      ready ||= initialize();
      const py = await ready;
      py.globals.set("request_json", JSON.stringify(request));
      py.globals.set("engine_progress", (done, total) =>
        self.postMessage({
          status: `Evaluating simulations: ${done} of ${total}…`,
        }),
      );
      const result = JSON.parse(
        py.runPython("dispatch(request_json, engine_progress)"),
      );
      self.postMessage({ id, result });
    } catch (error) {
      self.postMessage({ id, error: String(error.message || error) });
    }
  });
};
