"use client";

import { useEffect } from "react";

export function PwaRegister() {
  useEffect(() => {
    const secureContext = window.location.protocol === "https:" || window.location.hostname === "localhost";
    if ("serviceWorker" in navigator && secureContext) {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }
  }, []);
  return null;
}
