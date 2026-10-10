<template>
  <cv-grid fullWidth>
    <cv-row
      ><cv-column class="page-title"
        ><h2>{{ $t("administration.title") }}</h2></cv-column
      ></cv-row
    >
    <cv-row
      ><cv-column>
        <NsInlineNotification
          v-if="error"
          kind="error"
          title="C1 status unavailable"
          :description="error"
          :showCloseButton="false"
        />
        <NsTile v-if="integration" light>
          <p>
            {{
              integration.configured
                ? "C1 is ready."
                : "Administrator enrollment or recovery is pending."
            }}
          </p>
          <p v-if="integration.administration_url">
            <a
              :href="integration.administration_url"
              target="_blank"
              rel="noopener noreferrer"
              >Open C1 Explorer</a
            >
          </p>
          <p>
            Sign in with the existing domain account. Only the explicitly
            approved administrator can confirm initial enrollment. C1
            permissions are managed in Explorer.
          </p>
          <ul>
            <li v-for="blocker in integration.blockers" :key="blocker">
              {{ blocker }}
            </li>
          </ul>
        </NsTile>
      </cv-column></cv-row
    >
  </cv-grid>
</template>
<script>
import { mapState } from "vuex";
import { QueryParamService, PageTitleService } from "@nethserver/ns8-ui-lib";
import ModuleTasks from "../mixins/moduleTasks";
export default {
  name: "Administration",
  mixins: [QueryParamService, PageTitleService, ModuleTasks],
  pageTitle() {
    return this.$t("administration.title") + " - " + this.appName;
  },
  data() {
    return {
      q: { page: "administration" },
      urlCheckInterval: null,
      integration: null,
      error: "",
    };
  },
  computed: { ...mapState(["instanceName", "core", "appName"]) },
  created() {
    this.runModuleTask("get-integration-status")
      .then((result) => {
        this.integration = result;
      })
      .catch((error) => {
        this.error = this.getErrorMessage(error);
      });
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
};
</script>
<style scoped lang="scss">
@import "../styles/carbon-utils";
</style>
