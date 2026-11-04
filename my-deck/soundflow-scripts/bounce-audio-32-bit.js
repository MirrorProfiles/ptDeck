
/* sf.ui.proTools.trackGetByName({ name: "-OUT MASTER", makeVisible: true }).track.trackInsertToggleBypass({
    insertNumber: 9,
}); */

sf.ui.proTools.menuClick({
    menuPath: ["File","Bounce Mix..."],
});

sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Location").first.radioButtons.whoseTitle.is("Session Folder:").first.elementClick();

sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.checkBoxes.whoseTitle.is("Offline").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Location").first.checkBoxes.whoseTitle.is("Import After Bounce").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Audio").first.checkBoxes.whoseTitle.is("Add MP3").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Audio").first.popupButtons.allItems[3].popupMenuSelect({
    menuPath: ["44.1 kHz"],
});

sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Audio").first.popupButtons.allItems[2].popupMenuSelect({
    menuPath: ["32 Bit Float"],
});

