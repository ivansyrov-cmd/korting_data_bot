"use strict";

const PREVIEW_COUNT = 3;
const state = {
  data: null,
  activeCategory: "",
  query: "",
  expandAll: false,
};

const elements = {
  catalog: document.getElementById("catalog"),
  categoryTitle: document.getElementById("category-title"),
  collapseAll: document.getElementById("collapse-all"),
  empty: document.getElementById("empty"),
  search: document.getElementById("search"),
  summary: document.getElementById("summary"),
  tabs: document.getElementById("tabs"),
  template: document.getElementById("product-template"),
  updated: document.getElementById("updated"),
};

function normalize(value) {
  return String(value || "")
    .toLocaleLowerCase("ru")
    .replaceAll("ё", "е")
    .replace(/\s+/g, " ")
    .trim();
}

function searchableText(product) {
  return normalize([
    product.model,
    product.name,
    product.category,
    ...(product.usps || []).flatMap((usp) => [
      usp.title,
      usp.description,
      usp.glossary_title,
    ]),
  ].join(" "));
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(date);
}

function visibleProducts() {
  const query = normalize(state.query);
  return state.data.products.filter((product) => {
    const inCategory =
      state.activeCategory === "all" ||
      product.category === state.activeCategory;
    return inCategory && (!query || product._search.includes(query));
  });
}

function makeTab(label, value, count) {
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.category = value;
  button.setAttribute("role", "tab");
  button.setAttribute(
    "aria-selected",
    String(state.activeCategory === value),
  );
  button.append(document.createTextNode(label));
  const badge = document.createElement("span");
  badge.className = "tab-count";
  badge.textContent = count;
  button.appendChild(badge);
  button.addEventListener("click", () => {
    state.activeCategory = value;
    state.expandAll = false;
    render();
    window.scrollTo({
      top: document.querySelector(".controls").offsetTop,
      behavior: "smooth",
    });
  });
  return button;
}

function renderTabs() {
  elements.tabs.innerHTML = "";
  elements.tabs.setAttribute("role", "tablist");
  const total = state.data.products.length;
  elements.tabs.appendChild(makeTab("Все", "all", total));
  for (const category of state.data.categories) {
    elements.tabs.appendChild(
      makeTab(category.name, category.name, category.count),
    );
  }
}

function makeUsp(usp, index) {
  const item = document.createElement("section");
  item.className = "usp";
  if (index >= PREVIEW_COUNT) item.classList.add("is-extra");
  if (!usp.description) item.classList.add("usp--no-description");

  const title = document.createElement("h4");
  title.textContent = usp.title;
  item.appendChild(title);

  if (usp.description) {
    const description = document.createElement("p");
    description.textContent = usp.description;
    item.appendChild(description);
  }
  return item;
}

function updateCardButton(card, button, count) {
  const expanded = card.classList.contains("is-expanded");
  button.setAttribute("aria-expanded", String(expanded));
  button.textContent = expanded
    ? "Свернуть преимущества"
    : `Показать все преимущества (${count})`;
}

function makeCard(product) {
  const card = elements.template.content.firstElementChild.cloneNode(true);
  const visual = card.querySelector(".product-card__visual");
  const image = card.querySelector("img");
  const category = card.querySelector(".product-card__category");
  const count = card.querySelector(".product-card__count");
  const model = card.querySelector(".product-card__model");
  const name = card.querySelector(".product-card__name");
  const uspList = card.querySelector(".usp-list");
  const button = card.querySelector(".show-more");

  visual.href = product.url || "#";
  if (!product.url) {
    visual.removeAttribute("target");
    visual.setAttribute("aria-disabled", "true");
    visual.addEventListener("click", (event) => event.preventDefault());
  }
  if (product.photo) {
    image.src = product.photo;
    image.alt = product.name || product.model;
    image.addEventListener("load", () => visual.classList.add("has-image"));
    image.addEventListener("error", () => {
      image.removeAttribute("src");
      image.alt = "";
      visual.classList.remove("has-image");
    });
  } else {
    image.removeAttribute("src");
    image.alt = "";
  }

  category.textContent = product.category;
  count.textContent = `${product.usps.length} USP`;
  model.textContent = product.model;
  name.textContent =
    product.name && normalize(product.name) !== normalize(product.model)
      ? product.name
      : "";
  name.hidden = !name.textContent;

  product.usps.forEach((usp, index) => {
    uspList.appendChild(makeUsp(usp, index));
  });

  if (state.expandAll) card.classList.add("is-expanded");
  if (product.usps.length <= PREVIEW_COUNT) {
    button.hidden = true;
  } else {
    updateCardButton(card, button, product.usps.length);
    button.addEventListener("click", () => {
      card.classList.toggle("is-expanded");
      updateCardButton(card, button, product.usps.length);
    });
  }
  return card;
}

function renderCards() {
  const products = visibleProducts();
  const fragment = document.createDocumentFragment();
  for (const product of products) fragment.appendChild(makeCard(product));
  elements.catalog.replaceChildren(fragment);
  elements.empty.hidden = products.length > 0;
  elements.catalog.hidden = products.length === 0;

  const total = state.data.products.length;
  elements.summary.textContent =
    products.length === total
      ? `${total} моделей`
      : `Найдено: ${products.length} из ${total}`;
  elements.categoryTitle.textContent =
    state.activeCategory === "all"
      ? "Все модели"
      : state.activeCategory;
  elements.collapseAll.textContent = state.expandAll
    ? "Свернуть описания"
    : "Развернуть все описания";
  elements.collapseAll.hidden = products.length === 0;
}

function render() {
  renderTabs();
  renderCards();
}

elements.search.addEventListener("input", () => {
  state.query = elements.search.value;
  if (state.query.trim()) state.activeCategory = "all";
  state.expandAll = false;
  render();
});

elements.collapseAll.addEventListener("click", () => {
  state.expandAll = !state.expandAll;
  renderCards();
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    elements.search.focus();
  }
  if (event.key === "Escape" && document.activeElement === elements.search) {
    elements.search.value = "";
    state.query = "";
    elements.search.blur();
    render();
  }
});

async function start() {
  try {
    const response = await fetch("catalog.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    state.data.products.forEach((product) => {
      product._search = searchableText(product);
    });
    state.activeCategory =
      state.data.categories[0]?.name || "all";
    const generated = formatDate(state.data.generated);
    const feedDate = formatDate(state.data.feed_date);
    elements.updated.textContent = [
      generated && `Обновлено ${generated}`,
      feedDate && `фид от ${feedDate}`,
    ].filter(Boolean).join(" · ");
    render();
  } catch (error) {
    console.error(error);
    elements.summary.textContent = "Ошибка загрузки";
    elements.empty.hidden = false;
    elements.empty.querySelector("h2").textContent =
      "Не удалось загрузить каталог";
    elements.empty.querySelector("p").textContent =
      "Обновите страницу или попробуйте открыть её позже.";
  }
}

start();
