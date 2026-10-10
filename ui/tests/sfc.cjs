// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the shipped combo-box lifecycle in a DOM; visual widgets are stubbed.
const fs = require("node:fs");
const { createRequire } = require("node:module");
const path = require("node:path");
const uiRoot = path.resolve(__dirname, "..");
const uiRequire = createRequire(path.join(uiRoot, "package.json"));
const { JSDOM } = require("jsdom");
const dom = new JSDOM("<!doctype html><html><body></body></html>");
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
const Vue = uiRequire("vue/dist/vue.common.js");
Vue.config.productionTip = false;
Vue.config.devtools = false;
const babel = uiRequire("@babel/core");
function loadSfc(path, imports) {
  const source = fs.readFileSync(path, "utf8");
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
  const code = babel.transformSync(script, {
    configFile: false,
    babelrc: false,
    plugins: [uiRequire.resolve("@babel/plugin-transform-modules-commonjs")],
  }).code;
  const mod = { exports: {} };
  new Function("require", "module", "exports", code)(
    (id) => (id in imports ? imports[id] : uiRequire(id)),
    mod,
    mod.exports
  );
  return {
    component: mod.exports.default,
    template: source.match(/<template>([\s\S]*?)<\/template>/)[1],
  };
}
const combo = loadSfc(
  path.join(
    uiRoot,
    "node_modules/@nethserver/ns8-ui-lib/src/lib-components/NsComboBox.vue"
  ),
  {
    "@carbon/vue/src/mixins": {
      themeMixin: {},
      uidMixin: {},
      carbonPrefixMixin: {},
      methodsMixin: () => ({}),
    },
    "@carbon/icons-vue": {},
    "@carbon/icons-vue/es/chevron--down/16": {},
    "@carbon/icons-vue/es/close/16": {},
  }
).component;
combo.render = function (h) {
  return h("input", {
    attrs: { "data-title": this.title },
    domProps: { value: this.filter },
  });
};
const settings = loadSfc(path.join(uiRoot, "src/views/Settings.vue"), {
  "@nethserver/ns8-ui-lib": { QueryParamService: {}, PageTitleService: {} },
  "../mixins/moduleTasks": {},
});
settings.component.template = settings.template;
settings.component.computed = {
  providerOptions: settings.component.computed.providerOptions,
  domainOptions: settings.component.computed.domainOptions,
};
settings.component.components = { NsComboBox: combo };
for (const name of [
  "cv-grid",
  "cv-row",
  "cv-column",
  "cv-form",
  "NsTile",
  "NsInlineNotification",
  "NsProgressBar",
  "NsTextInput",
  "NsCheckbox",
  "cv-text-area",
  "NsButton",
]) {
  settings.component.components[name] = {
    props: ["value", "disabled", "loading", "label", "title", "description"],
    render(h) {
      return h(name === "cv-form" ? "form" : "div", this.$slots.default);
    },
  };
}
module.exports = { Vue, settings: settings.component };
