function ipcOk(data) {
  return { ok: true, data };
}

function ipcErr(error) {
  return { ok: false, error: String(error) };
}

function wrapIpcSync(fn) {
  return (...args) => {
    try {
      return ipcOk(fn(...args));
    } catch (err) {
      return ipcErr(err);
    }
  };
}

function wrapIpcAsync(fn) {
  return async (...args) => {
    try {
      return ipcOk(await fn(...args));
    } catch (err) {
      return ipcErr(err);
    }
  };
}

module.exports = {
  ipcOk,
  ipcErr,
  wrapIpcSync,
  wrapIpcAsync,
};
