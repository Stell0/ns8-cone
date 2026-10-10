# NS8 cone UI development

To develop cone UI please refer to [this section of the Developer manual](https://nethserver.github.io/ns8-core/ui/modules/#module-ui-development).

Run `corepack yarn test:settings` after installing the locked dependencies. These
DOM regression checks use the shipped `NsComboBox` lifecycle and test saved-value
loading, save/reload, and unavailable identity discovery. They mock NS8 tasks and
do not establish live browser or OAuth interoperability.
