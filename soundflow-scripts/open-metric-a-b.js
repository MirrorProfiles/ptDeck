
/* //Calling command "Open Insert by Plugin Name" from package "Pro Tools" (installed from user/pkg/version "srAasovvDiQacRZ2mcId4RrOA8R2/ckp49i4j60000a2100yfwywgf/cmkn26ec60003l3s2rnc99bdj")
sf.soundflow.runCommand({
    commandId: 'user:ckp49i4j60000a2100yfwywgf:ckftmxoe70002vz10iugti4kc',
    props: {
        track: sf.ui.proTools.trackGetByName({ name: "-OUT MASTER", makeVisible: true }).track,
        pluginName: "ADPTR MetricAB",
    }
}); */

sf.ui.proTools.trackGetByName({ name: "-OUT MASTER", makeVisible: true }).track.trackInsertToggleShow({
    insertNumber: 8,
    targetValue: "Toggle",
});

