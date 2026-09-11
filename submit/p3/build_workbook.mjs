import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';

const here=path.dirname(fileURLToPath(import.meta.url));
const arg=(name,fallback)=>{const i=process.argv.indexOf(name);return i<0?fallback:process.argv[i+1];};
const root=arg('--root',path.join(here,'source'));
const output=arg('--output-dir',here);
const previews=path.join(here,'previews');
await fs.mkdir(previews,{recursive:true});

const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'附件','附件3','result3.xlsx')));
const sheet=wb.worksheets.getItemAt(0);
if(process.argv.includes('--preview')){
  const image=await wb.render({sheetName:sheet.name,range:'A1:F5',scale:1.5,format:'png'});
  await fs.writeFile(path.join(previews,'template.png'),new Uint8Array(await image.arrayBuffer()));
}else{
  const data=JSON.parse(await fs.readFile(path.join(here,'result3_data.json'),'utf8'));
  const last=data.t_s.length+1;
  sheet.getRange('A1:V1').values=[['时间\\到药材中心的距离',...data.r_cm]];
  sheet.getRange(`A2:V${last}`).values=data.t_s.map((t,i)=>[t,...data.C[i]]);
  sheet.getRange(`A1:V${last}`).format.font={name:'宋体',size:10};
  sheet.getRange(`A1:V${last}`).format.horizontalAlignment='center';
  sheet.getRange(`A1:V${last}`).format.verticalAlignment='center';
  sheet.getRange(`A1:V${last}`).format.rowHeight=16;
  sheet.getRange(`A1:A${last}`).format.columnWidth=24;
  sheet.getRange(`B1:V${last}`).format.columnWidth=10;
  sheet.getRange('A1').format.wrapText=true;
  sheet.getRange('A1:V1').format.rowHeight=32;
  sheet.getRange(`A2:A${last-1}`).setNumberFormat('0');
  sheet.getRange(`A${last}`).setNumberFormat('0.0000');
  sheet.getRange('B1:V1').setNumberFormat('0.0');
  sheet.getRange(`B2:V${last}`).setNumberFormat('0.0000');
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
  wb.recalculate();
  for(const [label,range] of [['header','A1:H7'],['final',`A${last-5}:H${last}`],['surface',`O${last-5}:V${last}`]]){
    const image=await wb.render({sheetName:sheet.name,range,scale:1.5,format:'png'});
    await fs.writeFile(path.join(previews,label+'.png'),new Uint8Array(await image.arrayBuffer()));
  }
  console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NUM!|#N/A',options:{useRegex:true,maxResults:5},maxChars:500})).ndjson);
  await fs.mkdir(output,{recursive:true});
  const file=await SpreadsheetFile.exportXlsx(wb);
  await file.save(path.join(output,'result3.xlsx'));
  console.log('Saved result3.xlsx');
}
process.exit(0);
