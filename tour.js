const scenes = {
  browse: [
    "Files",
    "Two Prism panes show the Dovetail project and its Editions folder.",
    "Compare the project and its print editions in two independently navigable panes.",
  ],
  terminal: [
    "Terminal",
    "A native shell beneath two file panes lists the print editions.",
    "Run a shell command in the project while both folder panes stay in view.",
  ],
  editor: [
    "Editor",
    "The built-in editor displays the Edition Swift source for the sample print studio.",
    "Read and edit the source alongside the rest of your workspace.",
  ],
  space: [
    "Space",
    "The Space page maps the measured folders and files of the print studio.",
    "See how much room the artwork and editions occupy in this folder.",
  ],
};
const detailSizes = {
  browse: [542, 816],
  terminal: [660, 476],
  editor: [688, 840],
  space: [562, 872],
};
const controls = document.querySelector(".tabs");
const links = [...controls.querySelectorAll("a")];
let choice = 0;
let generation = 0;
function selectScene(link) {
  const ticket = ++generation;
  const key = link.dataset.scene;
  const [title, description, caption] = scenes[key];
  const detailURL = new URL(key + "-detail.jpg", link.href).href;
  const next = new Image();
  next.onload = () => {
    if (generation !== ticket) return;
    const shot = document.getElementById("shot");
    const detail = document.getElementById("shot-detail");
    detail.srcset = detailURL;
    detail.setAttribute("width", detailSizes[key][0]);
    detail.setAttribute("height", detailSizes[key][1]);
    shot.src = link.href;
    shot.alt = description;
    document.getElementById("detail-title").textContent = title + ", closer";
    document.getElementById("shot-link").href = link.href;
    document.getElementById("shot-link").setAttribute("aria-label", "Open full-size " + title + " screenshot");
    document.getElementById("full").href = link.href;
    document.getElementById("caption").textContent = caption;
    for (const item of links) {
      if (item === link) item.setAttribute("aria-current", "true");
      else item.removeAttribute("aria-current");
    }
  };
  next.onerror = () => {
    if (generation === ticket)
      document.getElementById("caption").textContent = "This image could not load. Select the view to try again.";
  };
  next.src = window.matchMedia("(max-width: 600px)").matches ? detailURL : link.href;
}
links.forEach((link, index) => {
  link.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    choice = index;
    selectScene(link);
  });
  link.addEventListener("keydown", (event) => {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    choice =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? links.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + links.length) % links.length;
    links[choice].focus();
    selectScene(links[choice]);
  });
});
