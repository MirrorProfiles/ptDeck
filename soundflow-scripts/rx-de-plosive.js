
sf.ui.proTools.audioSuiteOpenPlugin({
    category: "iZotope",
    name: "RX 11 De-plosive",
});

sf.ui.proTools.firstAudioSuiteWindow.audioSuiteSelectPreset({
    presetMenuPath: ["EAS Default"],
});

sf.ui.proTools.firstAudioSuiteWindow.audioSuiteRender();

//Calling command "Close First AudioSuite plugin" from package "Pro Tools" (installed from user/pkg/version "srAasovvDiQacRZ2mcId4RrOA8R2/ckp49i4j60000a2100yfwywgf/cmkn26ec60003l3s2rnc99bdj")
sf.soundflow.runCommand({
    commandId: 'user:ckp49i4j60000a2100yfwywgf:ckydgt59600003110hy9vb7kb',
    props: {}
});

