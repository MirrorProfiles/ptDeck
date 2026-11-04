//Calling command "2025 Import Session Data" from package "EAS"
sf.soundflow.runCommand({
    commandId: 'package:cm60ualsq0008t210zk6b1be6',
    props: {}
});

/* //Calling command "Import - Session Data..." from package "Pro Tools" (installed from user/pkg/version "srAasovvDiQacRZ2mcId4RrOA8R2/ckp49i4j60000a2100yfwywgf/cmkn26ec60003l3s2rnc99bdj")
sf.soundflow.runCommand({
    commandId: 'user:ckp49i4j60000a2100yfwywgf:cktcnf0ra000x9r109i8wen1u#cktcmsijz000i9r100tqfofgw',
    props: {}
}); */

/* sf.wait({
    intervalMs: 5000,
}); */

/* //Calling command "EAS SESSION DATA" from package "EAS"
sf.soundflow.runCommand({
    commandId: 'package:clgwsts7t0000ky10pcjuy64o',
    props: {}
}); */

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.elementWaitFor();

sf.keyboard.press({
    keys: "cmd+a",
});

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.groups.whoseTitle.is("Session Data").first.checkBoxes.whoseTitle.is("HEAT Master Settings").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.groups.whoseTitle.is("Session Data").first.checkBoxes.whoseTitle.is("Tempo / Meter Map").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.groups.whoseTitle.is("Timecode Mapping Options").first.checkBoxes.whoseTitle.is("Adjust Session Start Time to Match Source Start Time").first.checkboxSet({
    targetValue: "Enable",
});

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.groups.whoseTitle.is("Session Data").first.checkBoxes.whoseTitle.is("Key Signature / Chord Map").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.groups.whoseTitle.is("Session Data").first.checkBoxes.whoseTitle.is("Memory Locations (Non-Markers)").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.groups.whoseTitle.is("Session Data").first.checkBoxes.whoseTitle.is("Window Configurations").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.groups.whoseTitle.is("Session Data").first.checkBoxes.whoseTitle.is("Mic PRE Settings").first.checkboxSet({
    targetValue: "Disable",
});

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.groups.whoseTitle.is("Main Playlist Options").first.radioButtons.whoseTitle.is("Do Not Import").first.elementClick();

sf.ui.proTools.windows.whoseTitle.is("Import Session Data").first.buttons.whoseTitle.is("OK").first.elementClick();
