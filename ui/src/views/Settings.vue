<template>
  <cv-grid fullWidth>
    <cv-row
      ><cv-column class="page-title"
        ><h2>{{ $t("settings.title") }}</h2></cv-column
      ></cv-row
    >
    <cv-row
      ><cv-column>
        <NsInlineNotification
          :kind="diagnostics.configured ? 'success' : 'info'"
          title="C1 configuration"
          :description="
            diagnostics.configured
              ? 'C1 is configured and ready.'
              : 'Save settings to initialize C1, then complete approved administrator enrollment.'
          "
          :showCloseButton="false"
        />
        <NsInlineNotification
          v-if="error"
          kind="error"
          :title="$t('error.error')"
          :description="error"
          :showCloseButton="false"
        />
        <NsTile light>
          <NsProgressBar
            v-if="!configurationLoaded && loading"
            :indeterminate="true"
          />
          <cv-form v-if="configurationLoaded" @submit.prevent="save">
            <NsTextInput
              v-model.trim="settings.host"
              :label="$t('settings.host')"
              :disabled="loading"
            />
            <NsCheckbox
              v-model="settings.lets_encrypt"
              :label="$t('settings.lets_encrypt')"
              :disabled="loading"
            />
            <NsComboBox
              v-model="settings.idp_provider"
              :title="$t('settings.idp_provider')"
              :label="$t('settings.select_provider')"
              :options="providerOptions"
              :disabled="loading"
            />
            <NsComboBox
              v-model="settings.user_domain"
              :title="$t('settings.user_domain')"
              :label="$t('settings.select_domain')"
              :options="domainOptions"
              :disabled="loading"
            />
            <NsCheckbox
              v-model="settings.explorer_enabled"
              :label="$t('settings.explorer_enabled')"
              :disabled="loading"
            />
            <NsCheckbox
              v-model="settings.independent_review"
              :label="$t('settings.independent_review')"
              :disabled="loading"
            />
            <NsTextInput
              v-for="field in numericFields"
              :key="field"
              v-model="settings[field]"
              type="number"
              :label="$t('settings.' + field)"
              :disabled="loading"
            />
            <cv-text-area
              v-model="issuerCaPem"
              :label="$t('settings.issuer_ca')"
              :helper-text="$t('settings.issuer_ca_help')"
              :disabled="loading"
            />
            <NsCheckbox
              v-model="clearIssuerCa"
              :label="$t('settings.clear_ca')"
              :disabled="loading"
            />
            <p v-if="diagnostics.issuer_ca_present">
              {{ $t("settings.ca_present") }}
            </p>
            <p>{{ $t("settings.enrollment_pending") }}</p>
            <NsButton
              kind="primary"
              type="submit"
              :loading="loading"
              :disabled="loading"
              >{{ $t("settings.save_draft") }}</NsButton
            >
            <p v-if="saved">{{ $t("settings.draft_saved") }}</p>
          </cv-form>
        </NsTile>
        <NsTile light class="diagnostics">
          <h3>{{ $t("settings.diagnostics") }}</h3>
          <dl>
            <dt>{{ $t("settings.issuer") }}</dt>
            <dd>{{ diagnostics.issuer || "—" }}</dd>
            <dt>{{ $t("settings.audience") }}</dt>
            <dd>{{ diagnostics.audience || "—" }}</dd>
            <dt>{{ $t("settings.instance_id") }}</dt>
            <dd>{{ diagnostics.instance_id || "—" }}</dd>
          </dl>
        </NsTile>
      </cv-column></cv-row
    >
  </cv-grid>
</template>
<script>
import { mapState } from "vuex";
import { QueryParamService, PageTitleService } from "@nethserver/ns8-ui-lib";
import moduleTasks from "../mixins/moduleTasks";
const numericFields = [
  "session_idle_s",
  "session_max_s",
  "query_candidate_limit",
  "max_readable_scopes",
  "query_time_budget_ms",
  "backend_timeout_s",
];
export default {
  name: "Settings",
  mixins: [moduleTasks, QueryParamService, PageTitleService],
  pageTitle() {
    return this.$t("settings.title") + " - " + this.appName;
  },
  data() {
    return {
      q: { page: "settings" },
      urlCheckInterval: null,
      settings: {},
      diagnostics: {},
      loading: true,
      configurationLoaded: false,
      error: "",
      saved: false,
      numericFields,
      providers: [],
      domains: [],
      issuerCaPem: "",
      clearIssuerCa: false,
    };
  },
  computed: {
    ...mapState(["instanceName", "core", "appName"]),
    providerOptions() {
      return this.providers.map((p) => ({
        name: p.module_id,
        value: p.module_id,
        label: p.host + " (" + p.module_id + ")",
      }));
    },
    domainOptions() {
      return this.domains.map((d) => ({ name: d, value: d, label: d }));
    },
  },
  beforeRouteEnter(to, from, next) {
    next((vm) => {
      vm.watchQueryData(vm);
      vm.urlCheckInterval = vm.initUrlBindingForApp(vm, vm.q.page);
    });
  },
  beforeRouteLeave(to, from, next) {
    clearInterval(this.urlCheckInterval);
    next();
  },
  created() {
    this.load();
  },
  methods: {
    async load() {
      this.loading = true;
      this.configurationLoaded = false;
      try {
        const [configuration, discovery] = await Promise.allSettled([
          this.runModuleTask("get-configuration"),
          this.runModuleTask("list-identity-options"),
        ]);
        if (configuration.status === "rejected") throw configuration.reason;
        const config = configuration.value;
        const options =
          discovery.status === "fulfilled"
            ? discovery.value
            : { providers: [], domains: [] };
        this.providers = [...options.providers];
        this.domains = [...options.domains];
        // Keep saved selections visible even when discovery is unavailable.
        if (
          config.settings.idp_provider &&
          !this.providers.some(
            (p) => p.module_id === config.settings.idp_provider
          )
        ) {
          this.providers.push({
            module_id: config.settings.idp_provider,
            host: config.issuer
              ? new URL(config.issuer).hostname
              : config.settings.idp_provider,
          });
        }
        if (
          config.settings.user_domain &&
          !this.domains.includes(config.settings.user_domain)
        ) {
          this.domains.push(config.settings.user_domain);
        }
        // NsComboBox resolves the display label when its value changes, not
        // when its options change. Mount with options before applying values.
        this.settings = {};
        this.configurationLoaded = true;
        await this.$nextTick();
        this.diagnostics = config;
        this.settings = { ...config.settings };
        numericFields.forEach((field) => {
          this.settings[field] = String(this.settings[field]);
        });
        if (discovery.status === "rejected") {
          this.error = this.getErrorMessage(discovery.reason);
        }
      } catch (error) {
        this.error = this.getErrorMessage(error);
      } finally {
        this.loading = false;
      }
    },
    async save() {
      this.loading = true;
      this.error = "";
      this.saved = false;
      try {
        const data = { ...this.settings };
        numericFields.forEach((field) => {
          data[field] = Number(data[field]);
        });
        if (this.clearIssuerCa) data.issuer_ca_pem = "";
        else if (this.issuerCaPem.trim())
          data.issuer_ca_pem = this.issuerCaPem.trim();
        const result = await this.runModuleTask("configure-module", data);
        this.saved = result.draft_saved === true;
        this.issuerCaPem = "";
        this.clearIssuerCa = false;
        await this.load();
      } catch (error) {
        this.error = error.validationErrors
          ? error.validationErrors
              .map((v) => this.$t("settings." + v.error))
              .join("; ")
          : this.getErrorMessage(error);
      } finally {
        this.loading = false;
      }
    },
  },
};
</script>
<style scoped lang="scss">
@import "../styles/carbon-utils";
.diagnostics {
  margin-top: 2rem;
}
dt {
  margin-top: 1rem;
  font-weight: bold;
}
dd {
  overflow-wrap: anywhere;
}
</style>
