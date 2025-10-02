function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

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

  let activeRect = null;
  let dragStart = null;

  function updateRectSizeFromVideo() {
    const videoWidth = video.videoWidth;
    const videoHeight = video.videoHeight;

    if (!videoWidth || !videoHeight) {
      return;
    }

    const scale = Math.min(1, videoWidth / 1080, videoHeight / 675);
    const cropWidth = (1080 * scale) / videoWidth;
    const cropHeight = (675 * scale) / videoHeight;

    rectangles.forEach((rect) => {
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
    activeRect = rect;
    dragStart = {
      clientX: event.clientX,
      clientY: event.clientY,
      left: rect.left,
      top: rect.top,
    };
    event.preventDefault();
  }

  function pointerMove(event) {
    if (!activeRect || !dragStart) {
      return;
    }

    const bounds = overlay.getBoundingClientRect();
    if (!bounds.width || !bounds.height) {
      return;
    }

    const deltaX = (event.clientX - dragStart.clientX) / bounds.width;
    const deltaY = (event.clientY - dragStart.clientY) / bounds.height;

    activeRect.left = clamp(dragStart.left + deltaX, 0, 1 - activeRect.widthRatio);
    activeRect.top = clamp(dragStart.top + deltaY, 0, 1 - activeRect.heightRatio);

    paintRect(activeRect);
  }

  function endDrag(event) {
    activeRect = null;
    dragStart = null;
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
