"use strict";

if (typeof document === "undefined") {
  require("../../app.js");
} else {
  const script = document.createElement("script");
  script.src = "catalog.js";
  script.defer = true;
  document.head.appendChild(script);
}
