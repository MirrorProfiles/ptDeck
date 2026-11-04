
//Calling command "RS_Route Selected Tracks to Output" from package "Raphael Sepulveda Utilities" (installed from user/pkg/version "wumCaKnhA0T91I79tL1NbXLQmH03/ckijqv49o000b4z10qr66346e/cmpj3vi5u0000dz13eki8566d")
sf.soundflow.runCommand({
    commandId: 'user:clgxr9say000chg10uyi4ma5h:ckitegbf00006qm10ixs68zih',
    props: {
        outputPath: ["Stereo","bus","[DRUMS]"],
    }
});

/* //Calling command "Add Send on Next Available Slot" from package "Pro Tools" (installed from user/pkg/version "srAasovvDiQacRZ2mcId4RrOA8R2/ckp49i4j60000a2100yfwywgf/cmkn26ec60003l3s2rnc99bdj")
sf.soundflow.runCommand({
    commandId: 'user:ckp49i4j60000a2100yfwywgf:cko2k3o9r0001zu10nq6d5efx',
    props: {
        sendPath: ["Stereo","bus","//[PARA DRUMS]"],
    }
}); */

/* //Calling command "Assign //[PARA DRUMS] for selected tracks" from package "EAS"
sf.soundflow.runCommand({
    commandId: 'package:clgxtzgj2000nhg10s46ym9kq',
    props: {}
}); */

sf.ui.proTools.selectedTrack.trackInsertOrSendSelect({
    insertOrSend: "Send",
    pluginNumber: 1,
    pluginPath: ["Stereo","bus","//[PARA DRUMS]"],
    selectForAllSelectedTracks: true,
});

sf.ui.proTools.selectedTrack.trackInsertOrSendSelect({
    insertOrSend: "Send",
    pluginNumber: 2,
    pluginPath: ["Stereo","bus","//[1176CRUSH]"],
    selectForAllSelectedTracks: true,
});

sf.ui.proTools.selectedTrack.trackInsertOrSendSelect({
    insertOrSend: "Send",
    pluginNumber: 3,
    pluginPath: ["Stereo","bus","//[PARA DIST]"],
    selectForAllSelectedTracks: true,
});

