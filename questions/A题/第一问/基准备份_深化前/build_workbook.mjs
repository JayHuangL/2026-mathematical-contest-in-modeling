import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(here);
const outputDir = path.join(root, 'outputs', 'q1');
const previewDir = path.join(here, 'previews');
await fs.mkdir(previewDir, { recursive: true });
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root, '附件', '附件3', 'result1.xlsx')));
if (process.argv.includes('--preview')) {
  console.log((await wb.inspect({kind:'workbook,sheet,table',maxChars:1800,tableMaxRows:3,tableMaxCols:6})).ndjson);
  for (const name of ['温度', '水分浓度']) {
    const image = await wb.render({sheetName:name,range:'A1:F5',scale:1.5,format:'png'});
    await fs.writeFile(path.join(previewDir, `template_${name}.png`), new Uint8Array(await image.arrayBuffer()));
  }
} else {
  const data = JSON.parse(await fs.readFile(path.join(here, 'result1_data.json'), 'utf8'));
  for (const [name, key] of [['温度', 'T'], ['水分浓度', 'C']]) {
    const sheet = wb.worksheets.getItem(name);
    sheet.getRange('A1:V1').values = [['时间\\到药材中心的距离', ...data.r_cm]];
    sheet.getRange('A2:V1801').values = data.t_s.map((t, i) => [t, ...data[key][i]]);
    // Extend the template's centered Song typeface and numeric data layout.
    const used = sheet.getRange('A1:V1801');
    used.format.font = {name:'宋体', size:10};
    used.format.horizontalAlignment = 'center';
    used.format.verticalAlignment = 'center';
    used.format.rowHeight = 16;
    sheet.getRange('A1:A1801').format.columnWidth = 24;
    sheet.getRange('B1:V1801').format.columnWidth = 10;
    sheet.getRange('A1').format.wrapText = true;
    sheet.getRange('A1:V1').format.rowHeight = 32;
    sheet.getRange('A2:A1801').setNumberFormat('0');
    sheet.getRange('B1:V1').setNumberFormat('0.0');
    sheet.getRange('B2:V1801').setNumberFormat('0.0000');
    sheet.freezePanes.freezeRows(1);
    sheet.freezePanes.freezeColumns(1);
  }
  wb.recalculate();
  for (const name of ['温度', '水分浓度']) {
    console.log((await wb.inspect({kind:'table',range:`'${name}'!A1799:V1801`,include:'values',tableMaxRows:3,tableMaxCols:4,maxChars:1200})).ndjson);
    const image = await wb.render({sheetName:name,range:'A1795:H1801',scale:1.5,format:'png'});
    await fs.writeFile(path.join(previewDir, `result_${name}.png`), new Uint8Array(await image.arrayBuffer()));
    const header = await wb.render({sheetName:name,range:'A1:H7',scale:1.5,format:'png'});
    await fs.writeFile(path.join(previewDir, `header_${name}.png`), new Uint8Array(await header.arrayBuffer()));
  }
  console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
  await fs.mkdir(outputDir, {recursive:true});
  const file = await SpreadsheetFile.exportXlsx(wb);
  await file.save(path.join(outputDir, 'result1.xlsx'));
  console.log(`Saved ${path.join(outputDir, 'result1.xlsx')}`);
}
// All exports and writes are awaited before terminating the native rendering runtime.
process.exit(0);
