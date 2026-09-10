import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(here);
const outputDir = path.join(root, 'outputs', 'q2');
const previewDir = path.join(here, 'previews');
await fs.mkdir(previewDir, { recursive: true });
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root, '附件', '附件3', 'result2.xlsx')));
if (process.argv.includes('--preview')) {
  console.log((await wb.inspect({kind:'workbook,sheet,table', maxChars:1800, tableMaxRows:3, tableMaxCols:6})).ndjson);
  for (const name of ['温度', '水分浓度']) {
    const image = await wb.render({sheetName:name, range:'A1:F5', scale:1.5, format:'png'});
    await fs.writeFile(path.join(previewDir, `template_${name}.png`), new Uint8Array(await image.arrayBuffer()));
  }
} else {
  const data = JSON.parse(await fs.readFile(path.join(here, 'result2_data.json'), 'utf8'));
  const lastRow = data.t_s.length + 1;
  for (const [name, key] of [['温度', 'T'], ['水分浓度', 'C']]) {
    const sheet = wb.worksheets.getItem(name);
    sheet.getRange('A1:V1').values = [['时间\\到药材中心的距离', ...data.r_cm]];
    sheet.getRange(`A2:V${lastRow}`).values = data.t_s.map((t, i) => [t, ...data[key][i]]);
    const used = sheet.getRange(`A1:V${lastRow}`);
    used.format.font = {name:'宋体', size:10};
    used.format.horizontalAlignment = 'center';
    used.format.verticalAlignment = 'center';
    used.format.rowHeight = 16;
    sheet.getRange(`A1:A${lastRow}`).format.columnWidth = 24;
    sheet.getRange(`B1:V${lastRow}`).format.columnWidth = 10;
    sheet.getRange('A1').format.wrapText = true;
    sheet.getRange('A1:V1').format.rowHeight = 32;
    sheet.getRange(`A2:A${lastRow}`).setNumberFormat('0');
    sheet.getRange('B1:V1').setNumberFormat('0.0');
    sheet.getRange(`B2:V${lastRow}`).setNumberFormat('0.0000');
    sheet.freezePanes.freezeRows(1);
    sheet.freezePanes.freezeColumns(1);
  }
  wb.recalculate();
  for (const name of ['温度', '水分浓度']) {
    console.log((await wb.inspect({kind:'table', range:`'${name}'!A${lastRow-1}:D${lastRow}`,
                                  include:'values', tableMaxRows:2, tableMaxCols:4, maxChars:800})).ndjson);
    for (const [label, range] of [['header', 'A1:H7'], ['result', `O${lastRow-5}:V${lastRow}`]]) {
      const image = await wb.render({sheetName:name, range, scale:1.5, format:'png'});
      await fs.writeFile(path.join(previewDir, `${label}_${name}.png`), new Uint8Array(await image.arrayBuffer()));
    }
  }
  console.log((await wb.inspect({kind:'match', searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',
                                options:{useRegex:true, maxResults:10}, maxChars:600})).ndjson);
  await fs.mkdir(outputDir, {recursive:true});
  const file = await SpreadsheetFile.exportXlsx(wb);
  await file.save(path.join(outputDir, 'result2.xlsx'));
  console.log(`Saved ${path.join(outputDir, 'result2.xlsx')}`);
}
process.exit(0);
