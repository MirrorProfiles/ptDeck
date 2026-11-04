
sf.keyboard.press({
    keys: "ctrl+cmd+backslash",
});

sf.wait({
    intervalMs: 200,
});

sf.keyboard.press({
    keys: "alt+shift+r",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Replace").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.first.elementSetTextFieldWithAreaValue({
    value: "Edit.01",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.textFields.allItems[1].elementSetTextFieldWithAreaValue({
    value: "C",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Trim").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Add").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.checkBoxes.whoseTitle.is("Numbering").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Track Rename").first.buttons.whoseTitle.is("OK").first.elementClick();

