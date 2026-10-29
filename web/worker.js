// Runs Pyodide off the main thread so the page stays responsive during extraction.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js");

let pyodide;

async function init() {
  let start = performance.now();
  const lap = (label) => {
    const now = performance.now();
    postMessage({ log: `${label} (${((now - start) / 1000).toFixed(1)} s)` });
    start = now;
  };
  pyodide = await loadPyodide();
  lap("Python runtime loaded");
  await pyodide.loadPackage(["numpy", "opencv-python", "beautifulsoup4", "Pillow", "micropip"]);
  await pyodide.pyimport("micropip").install(["openpyxl", "xlsxwriter"]);
  lap("Packages installed");
  const [bundle, converter, browser] = await Promise.all(
    ["vendor/img2table.zip", "../converter.py", "browser.py"].map(async (path) => {
      const response = await fetch(path);
      if (!response.ok) throw new Error(`Cannot fetch ${path} (${response.status})`);
      return response.arrayBuffer();
    }),
  );
  pyodide.unpackArchive(bundle, "zip", { extractDir: "/app" });
  pyodide.FS.writeFile("/app/converter.py", new Uint8Array(converter));
  pyodide.FS.writeFile("/app/browser.py", new Uint8Array(browser));
  const contrib = pyodide.runPython("import cv2; hasattr(cv2, 'ximgproc')");  // Before browser.py shims it.
  pyodide.runPython("import sys; sys.path.insert(0, '/app'); import browser");
  lap("img2table imported");
  return { opencv: pyodide.runPython("cv2.__version__"), ximgproc: contrib };
}

const commands = {
  init,
  async pages({ text }) {
    return JSON.parse(pyodide.pyimport("browser").pages(text));
  },
  async start({ name }) {
    pyodide.pyimport("browser").start(name);
  },
  async ocrInput({ data, name, rotation }) {
    const browser = pyodide.pyimport("browser");
    const path = browser.ocr_input(data, name, rotation);
    return pyodide.FS.readFile(path);
  },
  async extract({ hocr, page, borderless, implicit, confidence }) {
    const browser = pyodide.pyimport("browser");
    const tables = JSON.parse(browser.extract(hocr, page, borderless, implicit, confidence));
    // The workbook covers every page extracted since start(), so return it whenever one exists.
    const xlsx = pyodide.FS.analyzePath("/tmp/tables.xlsx").exists ? pyodide.FS.readFile("/tmp/tables.xlsx") : null;
    return { tables, xlsx };
  },
};

onmessage = async ({ data: { id, command, args } }) => {
  try {
    postMessage({ id, result: await commands[command](args) });
  } catch (error) {
    console.error(error);
    // Python errors carry a full traceback; the page only needs its final line.
    const last = String(error.message || error).trim().split("\n").pop();
    postMessage({ id, error: last.replace(/^ValueError: /, "") });
  }
};
