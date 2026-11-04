
sf.ui.proTools.audioSuiteOpenPlugin({
    category: "Avid",
    name: "EQ3 7-Band",
});

sf.ui.proTools.firstAudioSuiteWindow.audioSuiteSelectPreset({
    presetMenuPath: ["EAS Bleed Filter"],
});

sf.ui.proTools.firstAudioSuiteWindow.audioSuiteRender();

//Calling command "Close First AudioSuite plugin" from package "Pro Tools" (installed from user/pkg/version "srAasovvDiQacRZ2mcId4RrOA8R2/ckp49i4j60000a2100yfwywgf/cmkn26ec60003l3s2rnc99bdj")
sf.soundflow.runCommand({
    commandId: 'user:ckp49i4j60000a2100yfwywgf:ckydgt59600003110hy9vb7kb',
    props: {}
});

sf.keyboard.press({
    keys: "ctrl+alt+shift+tab",
});

sf.ui.proTools.menuClick({
    menuPath: ["Edit","Fades","Create..."],
});

sf.wait({
    intervalMs: 500,
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Fade In Operation").first.checkBoxes.whoseTitle.is("Create new fade ins").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Fade In Operation").first.checkBoxes.whoseTitle.is("Adjust existing fade in shape & slope").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Fade In Operation").first.checkBoxes.whoseTitle.is("Adjust existing fade in length").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Crossfade Operation").first.checkBoxes.whoseTitle.is("Create new crossfades").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Crossfade Operation").first.checkBoxes.whoseTitle.is("Adjust existing crossfade shape & slope").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Crossfade Operation").first.checkBoxes.whoseTitle.is("Adjust existing crossfade length").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Fade Out Operation").first.checkBoxes.whoseTitle.is("Create new fade outs").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Fade Out Operation").first.checkBoxes.whoseTitle.is("Adjust existing fade out shape & slope").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Fade Out Operation").first.checkBoxes.whoseTitle.is("Adjust existing fade out length").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Fade In Operation").first.textFields.first.elementSetTextAreaValue({
    value: "1",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Crossfade Operation").first.textFields.first.elementSetTextAreaValue({
    value: "5",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.groups.whoseTitle.is("Fade Out Operation").first.textFields.first.elementSetTextAreaValue({
    value: "150",
});

sf.ui.proTools.windows.whoseTitle.is("Batch Fades").first.buttons.whoseTitle.is("OK").first.elementClick();

