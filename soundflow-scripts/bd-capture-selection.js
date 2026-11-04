
/* //Calling command "If Menu Item Is Enabled" from package "Basics" (installed from user/pkg/version "srAasovvDiQacRZ2mcId4RrOA8R2/ckuxffxq80000u010m7g02u3l/cmmthpowy00001zsyfs026r6w")
sf.soundflow.runCommand({
    commandId: 'user:ckuxffxq80000u010m7g02u3l:ckuxfj0cn0003u010jcnoh0dg',
    props: {}
}); */

sf.ui.proTools.viewCloseFloatingWindows();

//Calling command "Beat Detective" from package "Pro Tools" (installed from user/pkg/version "srAasovvDiQacRZ2mcId4RrOA8R2/ckp49i4j60000a2100yfwywgf/cmkn26ec60003l3s2rnc99bdj")
sf.soundflow.runCommand({
    commandId: 'user:ckp49i4j60000a2100yfwywgf:ckxzio5ll000pm110u770kza6#ckxzjz7xw001km110nzcjetlp',
    props: {}
});

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Operation").first.radioButtons.whoseTitle.is("Clip Separation").first.elementClick();

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Selection").first.popupButtons.first.popupMenuSelect({
    menuPath: ["1/16 Note"],
});

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Selection").first.buttons.whoseTitle.is("CheckBox").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Selection").first.buttons.whoseTitle.is("Capture Selection").first.elementClick();

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Detection:").first.textFields.whoseTitle.is("NumericEntryText").first.elementSetTextAreaValue({
    value: "33",
});

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Detection:").first.textFields.whoseTitle.is("NumericEntryText").allItems[1].elementSetTextAreaValue({
    value: "10",
});

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Detection:").first.radioButtons.whoseTitle.is("Sub-Beats").first.elementClick();

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Detection:").first.children.whoseRole.is("AXMenuButton").whoseTitle.is("Enhanced Resolution").first.popupMenuSelect({
    menuPath: ["Enhanced Resolution"],
});

sf.ui.proTools.windows.whoseTitle.is("Beat Detective").first.groups.whoseTitle.is("Detection:").first.buttons.whoseTitle.is("Analyze").first.elementClick();

