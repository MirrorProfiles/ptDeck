
//Calling command "Copy" from package "Pro Tools" (installed from user/pkg/version "srAasovvDiQacRZ2mcId4RrOA8R2/ckp49i4j60000a2100yfwywgf/cmkn26ec60003l3s2rnc99bdj")
sf.soundflow.runCommand({
    commandId: 'user:ckp49i4j60000a2100yfwywgf:ckt90h5f100008a10ilhfochy#ckt4xiomm00083n10ynrq3wsf',
    props: {}
});

sf.keyboard.press({
    keys: "ctrl+alt+backslash",
});

sf.wait();

(throw 'context missing').paste();

sf.keyboard.press({
    keys: "alt+shift+r",
});

sf.wait();

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Replace").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Trim").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Add").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Numbering").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Clear Existing Name").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Regular Expressions").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.first.elementClick();

sf.keyboard.type({
    text: "Comp",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.allItems[1].elementClick();

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.whoseValue.is("0").allItems[1].elementSetTextFieldWithAreaValue({
    value: "3",
});

/* (throw 'context missing').elementClick(); */

sf.keyboard.type({
    text: "Edited",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.buttons.whoseTitle.is("OK").first.elementClick();

sf.keyboard.press({
    keys: "ctrl+alt+backslash",
});

sf.wait();

(throw 'context missing').paste();

sf.keyboard.press({
    keys: "alt+shift+r",
});

sf.wait();

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.first.elementClick();

sf.keyboard.type({
    text: "Edited",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.allItems[1].elementClick();

sf.keyboard.type({
    text: "C",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Trim").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.allItems[3].elementClick();

sf.keyboard.type({
    text: "3",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.buttons.whoseTitle.is("OK").first.elementClick();

sf.ui.proTools.menuClick({
    menuPath: ["Edit","Consolidate Clip"],
});
