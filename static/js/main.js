function clamp(value, min, max) {
  if (min > max) {
    return min;
  }
  return Math.min(Math.max(value, min), max);
}

const TARGET_ASPECT = {
  width: 1100,
  height: 1000,
};

const TARGET_ASPECT_RATIO = TARGET_ASPECT.width / TARGET_ASPECT.height;

const HANDLE_POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right"];

document.addEventListener("DOMContentLoaded", () => {
  const video = document.getElementById("source-video");
  const overlay = document.getElementById("selection-overlay");
  const confirmButton = document.getElementById("confirm-selection");
  const feedback = document.getElementById("feedback");
  const exportsList = document.getElementById("exports");

  if (!video || !overlay) {
    return;
  }

  const rectangles = [
    {
      id: "rect-speaker-1",
      element: document.getElementById("rect-speaker-1"),
      defaultLeft: 0.05,
      defaultTop: 0.1,
      left: null,
      top: null,
      widthRatio: 0,
      heightRatio: 0,
    },
    {
      id: "rect-speaker-2",
      element: document.getElementById("rect-speaker-2"),
      defaultLeft: 0.6,
      defaultTop: 0.55,
      left: null,
      top: null,
      widthRatio: 0,
      heightRatio: 0,
    },
  ];

  let interaction = null;
  let minWidthRatio = 0.12;

  rectangles.forEach((rect) => {
    if (!rect.element) {
      return;
    }
    HANDLE_POSITIONS.forEach((position) => {
      const handle = document.createElement("span");
      handle.className = `selection-rect__handle selection-rect__handle--${position}`;
      handle.dataset.handle = position;
      handle.addEventListener("pointerdown", (event) => pointerDownResize(event, rect, position));
      rect.element.appendChild(handle);
    });
  });

  function getVideoMetrics() {
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) {
      return null;
    }
    return { width, height };
  }

  function updateRectSizeFromVideo() {
    const videoWidth = video.videoWidth;
    const videoHeight = video.videoHeight;

    if (!videoWidth || !videoHeight) {
      return;
    }

    // const scale = Math.min(1, videoWidth / TARGET_ASPECT.width, videoHeight / TARGET_ASPECT.height);
    // const cropWidth = (TARGET_ASPECT.width * scale) / videoWidth;
    // const cropHeight = cropWidth / TARGET_ASPECT_RATIO;
    const cropWidth = TARGET_ASPECT.width / videoWidth;
    const cropHeight = TARGET_ASPECT.height / videoHeight;

    minWidthRatio = Math.min(Math.max(cropWidth * 0.5, 0.03), cropWidth || 0.12);

    rectangles.forEach((rect) => {
      // if (!rect.widthRatio || !rect.heightRatio) {
      //   rect.widthRatio = cropWidth;
      //   rect.heightRatio = cropHeight;
      // } else {
      //   rect.heightRatio = rect.widthRatio / TARGET_ASPECT_RATIO;
      // }
      rect.widthRatio = cropWidth;
      rect.heightRatio = cropHeight;
      if (rect.left === null || rect.top === null) {
        rect.left = rect.defaultLeft;
        rect.top = rect.defaultTop;
      }
      rect.left = clamp(rect.left, 0, 1 - rect.widthRatio);
      rect.top = clamp(rect.top, 0, 1 - rect.heightRatio);
      paintRect(rect);
    });

    overlay.classList.remove("hidden");
  }

  function paintRect(rect) {
    if (!rect.element || rect.left === null || rect.top === null) {
      return;
    }

    rect.element.style.width = `${rect.widthRatio * 100}%`;
    rect.element.style.height = `${rect.heightRatio * 100}%`;
    rect.element.style.left = `${rect.left * 100}%`;
    rect.element.style.top = `${rect.top * 100}%`;
  }

  function pointerDown(event, rect) {
    if (rect.left === null || rect.top === null) {
      return;
    }
    interaction = {
      mode: "move",
      rect,
      start: {
        clientX: event.clientX,
        clientY: event.clientY,
        left: rect.left,
        top: rect.top,
      },
      pointerId: event.pointerId,
      capturedTarget: rect.element,
    };
    event.preventDefault();
    event.stopPropagation();
    if (typeof rect.element.setPointerCapture === "function") {
      rect.element.setPointerCapture(event.pointerId);
    }
  }

  function pointerDownResize(event, rect, handle) {
    if (rect.left === null || rect.top === null) {
      return;
    }
    const metrics = getVideoMetrics();
    if (!metrics) {
      return;
    }
    interaction = {
      mode: "resize",
      rect,
      handle,
      start: {
        leftRatio: rect.left,
        topRatio: rect.top,
        widthRatio: rect.widthRatio,
        heightRatio: rect.heightRatio,
        leftPx: rect.left * metrics.width,
        topPx: rect.top * metrics.height,
        widthPx: rect.widthRatio * metrics.width,
        heightPx: rect.heightRatio * metrics.height,
      },
      pointerId: event.pointerId,
      capturedTarget: event.currentTarget,
    };
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  }

  function pointerMove(event) {
    if (!interaction) {
      return;
    }

    if (interaction.mode === "move") {
      const bounds = overlay.getBoundingClientRect();
      if (!bounds.width || !bounds.height) {
        return;
      }

      const deltaX = (event.clientX - interaction.start.clientX) / bounds.width;
      const deltaY = (event.clientY - interaction.start.clientY) / bounds.height;

      interaction.rect.left = clamp(
        interaction.start.left + deltaX,
        0,
        1 - interaction.rect.widthRatio,
      );
      interaction.rect.top = clamp(
        interaction.start.top + deltaY,
        0,
        1 - interaction.rect.heightRatio,
      );

      paintRect(interaction.rect);
      return;
    }

    const point = getPointerRatio(event);
    if (!point) {
      return;
    }

    resizeRect(interaction, point);
    paintRect(interaction.rect);
  }

  function getPointerRatio(event) {
    const bounds = overlay.getBoundingClientRect();
    if (!bounds.width || !bounds.height) {
      return null;
    }
    return {
      x: clamp((event.clientX - bounds.left) / bounds.width, 0, 1),
      y: clamp((event.clientY - bounds.top) / bounds.height, 0, 1),
    };
  }

  function resizeRect(currentInteraction, pointRatio) {
    const rect = currentInteraction.rect;
    const start = currentInteraction.start;
    const metrics = getVideoMetrics();
    if (!metrics) {
      return;
    }

    const pointerPx = {
      x: pointRatio.x * metrics.width,
      y: pointRatio.y * metrics.height,
    };

    const minWidthPx = Math.max(Math.min(minWidthRatio, 1), 0.02) * metrics.width;

    const applyValues = (leftPx, topPx, widthPx) => {
      const boundedWidthPx = clamp(widthPx, minWidthPx, metrics.width);
      const heightPx = boundedWidthPx / TARGET_ASPECT_RATIO;
      const maxLeftPx = Math.max(metrics.width - boundedWidthPx, 0);
      const maxTopPx = Math.max(metrics.height - heightPx, 0);
      const safeLeftPx = clamp(leftPx, 0, maxLeftPx);
      const safeTopPx = clamp(topPx, 0, maxTopPx);
      rect.widthRatio = boundedWidthPx / metrics.width;
      rect.heightRatio = heightPx / metrics.height;
      rect.left = safeLeftPx / metrics.width;
      rect.top = safeTopPx / metrics.height;
    };

    const computeWidthPx = (dxPx, dyPx, boundPx) => {
      const widthFromX = Math.max(dxPx, 0);
      const widthFromY = Math.max(dyPx, 0) * TARGET_ASPECT_RATIO;
      const candidate = Math.min(widthFromX, widthFromY);
      const maxWidthPx = Math.max(Math.min(boundPx, metrics.width), minWidthPx);
      return clamp(candidate, minWidthPx, maxWidthPx);
    };

    switch (currentInteraction.handle) {
      case "top-left": {
        const anchorX = start.leftPx + start.widthPx;
        const anchorY = start.topPx + start.heightPx;
        const dxPx = anchorX - pointerPx.x;
        const dyPx = anchorY - pointerPx.y;
        const boundsWidthPx = Math.min(anchorX, anchorY * TARGET_ASPECT_RATIO);
        const newWidthPx = computeWidthPx(dxPx, dyPx, boundsWidthPx);
        const newLeftPx = anchorX - newWidthPx;
        const newTopPx = anchorY - newWidthPx / TARGET_ASPECT_RATIO;
        applyValues(newLeftPx, newTopPx, newWidthPx);
        break;
      }
      case "top-right": {
        const anchorX = start.leftPx;
        const anchorY = start.topPx + start.heightPx;
        const dxPx = pointerPx.x - anchorX;
        const dyPx = anchorY - pointerPx.y;
        const boundsWidthPx = Math.min(metrics.width - anchorX, anchorY * TARGET_ASPECT_RATIO);
        const newWidthPx = computeWidthPx(dxPx, dyPx, boundsWidthPx);
        const newLeftPx = anchorX;
        const newTopPx = anchorY - newWidthPx / TARGET_ASPECT_RATIO;
        applyValues(newLeftPx, newTopPx, newWidthPx);
        break;
      }
      case "bottom-left": {
        const anchorX = start.leftPx + start.widthPx;
        const anchorY = start.topPx;
        const dxPx = anchorX - pointerPx.x;
        const dyPx = pointerPx.y - anchorY;
        const boundsWidthPx = Math.min(anchorX, (metrics.height - anchorY) * TARGET_ASPECT_RATIO);
        const newWidthPx = computeWidthPx(dxPx, dyPx, boundsWidthPx);
        const newLeftPx = anchorX - newWidthPx;
        const newTopPx = anchorY;
        applyValues(newLeftPx, newTopPx, newWidthPx);
        break;
      }
      case "bottom-right": {
        const anchorX = start.leftPx;
        const anchorY = start.topPx;
        const dxPx = pointerPx.x - anchorX;
        const dyPx = pointerPx.y - anchorY;
        const boundsWidthPx = Math.min(
          metrics.width - anchorX,
          (metrics.height - anchorY) * TARGET_ASPECT_RATIO,
        );
        const newWidthPx = computeWidthPx(dxPx, dyPx, boundsWidthPx);
        const newLeftPx = anchorX;
        const newTopPx = anchorY;
        applyValues(newLeftPx, newTopPx, newWidthPx);
        break;
      }
      default:
        break;
    }
  }

  function endDrag(event) {
    if (interaction?.pointerId && interaction?.capturedTarget) {
      const target = interaction.capturedTarget;
      if (typeof target.releasePointerCapture === "function") {
        try {
          target.releasePointerCapture(interaction.pointerId);
        } catch (error) {
          // Pointer might already be released; ignore.
        }
      }
    }
    interaction = null;
  }

  rectangles.forEach((rect) => {
    if (!rect.element) {
      return;
    }
    rect.element.addEventListener("pointerdown", (event) => pointerDown(event, rect));
  });

  document.addEventListener("pointermove", pointerMove);
  document.addEventListener("pointerup", endDrag);
  document.addEventListener("pointercancel", endDrag);

  function renderAll() {
    rectangles.forEach(paintRect);
  }

  function resetFeedback() {
    feedback.textContent = "";
    feedback.className = "feedback";
    exportsList.innerHTML = "";
  }

  function setFeedback(message, status) {
    feedback.textContent = message;
    feedback.className = `feedback feedback--${status}`;
  }

  async function handleConfirm() {
    resetFeedback();
    setFeedback("Processing with ffmpeg…", "pending");
    confirmButton.disabled = true;

    try {
      const body = {
        regions: rectangles.map((rect) => ({
          id: rect.id,
          x: rect.left,
          y: rect.top,
          width: rect.widthRatio,
          height: rect.heightRatio,
        })),
      };

      const response = await fetch("/process", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || "Unable to process video");
      }

      const result = await response.json();
      const { outputs = [] } = result;

      if (!outputs.length) {
        setFeedback("Processing finished but no outputs were generated.", "warning");
        return;
      }

      setFeedback("Export complete!", "success");
      exportsList.innerHTML = outputs
        .map(
          (item) => `
            <article class="exports__item">
              <h3>${item.label}</h3>
              <p>Crop: ${item.crop.width}×${item.crop.height} @ (${item.crop.x}, ${item.crop.y})</p>
              <a href="${item.url}" class="download" download>Download clip</a>
            </article>
          `
        )
        .join("");
    } catch (error) {
      console.error(error);
      setFeedback(error.message, "error");
    } finally {
      confirmButton.disabled = false;
    }
  }

  confirmButton.addEventListener("click", handleConfirm);

  video.addEventListener("loadedmetadata", () => {
    updateRectSizeFromVideo();
    renderAll();
  });

  if (video.readyState >= 1) {
    updateRectSizeFromVideo();
    renderAll();
  }

  window.addEventListener("resize", renderAll);
});
