// SPDX-License-Identifier: GPL-3.0-or-later
import { TaskService, UtilService } from "@nethserver/ns8-ui-lib";
export default {
  mixins: [TaskService, UtilService],
  methods: {
    runModuleTask(action, data) {
      const eventId = this.getUuid();
      return new Promise((resolve, reject) => {
        const events = ["completed", "aborted", "validation-failed"].map(
          (state) => `${action}-${state}-${eventId}`
        );
        const cleanup = () =>
          events.forEach((event) => this.core.$root.$off(event));
        this.core.$root.$once(events[0], (context, result) => {
          cleanup();
          resolve(result.output);
        });
        this.core.$root.$once(events[1], () => {
          cleanup();
          reject(new Error(this.$t("error.generic_error")));
        });
        this.core.$root.$once(events[2], (errors) => {
          cleanup();
          const error = new Error(this.$t("error.validation_error"));
          error.validationErrors = errors;
          reject(error);
        });
        this.createModuleTaskForApp(this.instanceName, {
          action,
          data,
          extra: {
            title: this.$t("action." + action),
            isNotificationHidden: true,
            eventId,
          },
        }).catch((error) => {
          cleanup();
          reject(error);
        });
      });
    },
  },
};
