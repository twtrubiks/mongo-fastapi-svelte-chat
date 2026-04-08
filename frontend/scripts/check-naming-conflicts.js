#!/usr/bin/env node

/**
 * 自動檢查 Svelte 文件中的命名衝突
 * 使用方法: node scripts/check-naming-conflicts.js
 */

import fs from 'fs';
import { glob } from 'glob';

// 常見的 store 名稱
const COMMON_STORE_NAMES = [
  'currentUser',
  'currentRoom', 
  'roomList',
  'messageList',
  'messageLoading',
  'roomLoading',
  'userLoading'
];

// 檢查單個文件
function checkFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const issues = [];
  
  // 提取導入的變數
  const importRegex = /import\s*\{([^}]+)\}\s*from/g;
  const imports = new Set();
  let match;
  
  while ((match = importRegex.exec(content)) !== null) {
    const importList = match[1].split(',').map(s => s.trim());
    importList.forEach(imp => {
      const cleanImport = imp.replace(/\s+as\s+\w+/, '').trim();
      imports.add(cleanImport);
    });
  }
  
  // 檢查本地變數宣告
  const letRegex = /let\s+(\w+)/g;
  const constRegex = /const\s+(\w+)/g;
  const localVars = new Set();
  
  while ((match = letRegex.exec(content)) !== null) {
    localVars.add(match[1]);
  }
  
  while ((match = constRegex.exec(content)) !== null) {
    localVars.add(match[1]);
  }
  
  // 檢查函數宣告
  const functionRegex = /function\s+(\w+)/g;
  const localFunctions = new Set();
  
  while ((match = functionRegex.exec(content)) !== null) {
    localFunctions.add(match[1]);
  }
  
  // 檢查衝突
  for (const imported of imports) {
    if (localVars.has(imported)) {
      issues.push({
        type: 'VARIABLE_CONFLICT',
        name: imported,
        message: `導入的變數 '${imported}' 與本地變數衝突`
      });
    }
    
    if (localFunctions.has(imported)) {
      issues.push({
        type: 'FUNCTION_CONFLICT', 
        name: imported,
        message: `導入的變數 '${imported}' 與本地函數衝突`
      });
    }
  }
  
  // 檢查是否同時有變數和函數同名
  for (const varName of localVars) {
    if (localFunctions.has(varName)) {
      issues.push({
        type: 'LOCAL_CONFLICT',
        name: varName,
        message: `本地變數 '${varName}' 與本地函數同名`
      });
    }
  }
  
  // 檢查常見的 store 命名問題
  for (const storeName of COMMON_STORE_NAMES) {
    if (localVars.has(storeName) && imports.has(storeName)) {
      issues.push({
        type: 'STORE_CONFLICT',
        name: storeName,
        message: `可能的 store 衝突: '${storeName}' 同時被導入和本地宣告`
      });
    }
  }
  
  return issues;
}

// 主要檢查函數
function checkNamingConflicts() {
  console.log('🔍 正在檢查命名衝突...\n');
  
  // 找到所有 .svelte 文件
  const svelteFiles = glob.sync('src/**/*.svelte', { cwd: process.cwd() });
  
  let totalIssues = 0;
  let filesWithIssues = 0;
  
  for (const file of svelteFiles) {
    const issues = checkFile(file);
    
    if (issues.length > 0) {
      filesWithIssues++;
      totalIssues += issues.length;
      
      console.log(`❌ ${file}:`);
      for (const issue of issues) {
        const emoji = {
          'VARIABLE_CONFLICT': '🔴',
          'FUNCTION_CONFLICT': '🟠', 
          'LOCAL_CONFLICT': '🟡',
          'STORE_CONFLICT': '🔵'
        }[issue.type] || '⚪';
        
        console.log(`  ${emoji} ${issue.message}`);
      }
      console.log();
    }
  }
  
  // 總結報告
  console.log('📊 檢查完成!');
  console.log(`總共檢查了 ${svelteFiles.length} 個文件`);
  console.log(`發現 ${totalIssues} 個問題在 ${filesWithIssues} 個文件中`);
  
  if (totalIssues === 0) {
    console.log('✅ 沒有發現命名衝突問題！');
  } else {
    console.log('\n🛠️  建議修復這些問題以避免潛在的錯誤。');
    process.exit(1);
  }
}

// 如果直接執行此腳本
if (import.meta.url === `file://${process.argv[1]}`) {
  checkNamingConflicts();
}

export { checkNamingConflicts, checkFile };