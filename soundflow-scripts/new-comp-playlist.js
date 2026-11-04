
sf.keyboard.press({
    keys: "ctrl+backslash",
});

sf.wait({
    intervalMs: 200,
});

sf.keyboard.press({
    keys: "alt+shift+r",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Replace").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Trim").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.whoseValue.is("0").first.elementSetTextFieldWithAreaValue({
    value: "0",
});

sf.wait({
    intervalMs: 200,
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.whoseValue.is("0").allItems[1].elementSetTextFieldWithAreaValue({
    value: "2",
    useMouseKeyboard: true,
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Add").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Prefix:").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Insert:").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Suffix:").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.allItems[9].elementSetTextFieldWithAreaValue({
    value: "Comp",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.buttons.whoseTitle.is("OK").first.elementClick();
