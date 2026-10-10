// SPDX-License-Identifier: GPL-3.0-or-later
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { Vue, settings } = require("./sfc.cjs");
const values = {
  host: "cone.makako.sf.nethserver.net",
  idp_provider: "idp1",
  user_domain: "makako.sf.nethserver.net",
  lets_encrypt: true,
  explorer_enabled: true,
  independent_review: false,
  session_idle_s: 1800,
  session_max_s: 28800,
  query_candidate_limit: 5000,
  max_readable_scopes: 500,
  query_time_budget_ms: 10000,
  backend_timeout_s: 5,
};
const config = {
  settings: values,
  issuer:
    "https://idp.makako.sf.nethserver.net/realms/makako.sf.nethserver.net",
};
const options = {
  providers: [{ module_id: "idp1", host: "idp.makako.sf.nethserver.net" }],
  domains: ["makako.sf.nethserver.net"],
};
async function settle(vm) {
  for (let i = 0; i < 8; i++) {
    await Promise.resolve();
    await Vue.nextTick();
  }
  return vm;
}
function mount(failDiscovery = false) {
  const actions = [];
  const vm = new Vue({
    ...settings,
    methods: {
      ...settings.methods,
      $t: (x) => x,
      getErrorMessage: (e) => e.message,
      runModuleTask: async (action, data) => {
        actions.push({ action, data });
        if (action === "get-configuration") return config;
        if (action === "list-identity-options") {
          if (failDiscovery) throw Error("Discovery unavailable");
          return options;
        }
        if (action === "configure-module") {
          assert.deepEqual(data, values);
          return { draft_saved: true };
        }
        throw Error(action);
      },
    },
  }).$mount();
  document.body.appendChild(vm.$el);
  return { vm, actions };
}
function selections(vm) {
  return [...vm.$el.querySelectorAll("input")].map((x) => x.value);
}
test("saved identity labels load, including when returning to the page", async () => {
  for (let i = 0; i < 2; i++) {
    const { vm } = mount();
    await settle(vm);
    assert.deepEqual(selections(vm), [
      "idp.makako.sf.nethserver.net (idp1)",
      "makako.sf.nethserver.net",
    ]);
    assert.equal(vm.settings.host, values.host);
    assert.equal(vm.settings.lets_encrypt, true);
    assert.equal(vm.settings.independent_review, false);
    vm.$destroy();
    vm.$el.remove();
  }
});
test("saving and reloading preserves values, labels, and numeric types", async () => {
  const { vm, actions } = mount();
  await settle(vm);
  await vm.save();
  await settle(vm);
  assert.equal(vm.saved, true);
  assert.deepEqual(selections(vm), [
    "idp.makako.sf.nethserver.net (idp1)",
    "makako.sf.nethserver.net",
  ]);
  assert.equal(
    actions.filter((x) => x.action === "configure-module").length,
    1
  );
  assert.equal(vm.settings.session_idle_s, "1800");
  vm.$destroy();
  vm.$el.remove();
});
test("failed discovery retains saved selections and reports the failure", async () => {
  const { vm } = mount(true);
  await settle(vm);
  assert.deepEqual(selections(vm), [
    "idp.makako.sf.nethserver.net (idp1)",
    "makako.sf.nethserver.net",
  ]);
  assert.equal(vm.settings.host, values.host);
  assert.equal(vm.error, "Discovery unavailable");
  assert.equal(vm.loading, false);
  vm.$destroy();
  vm.$el.remove();
});
