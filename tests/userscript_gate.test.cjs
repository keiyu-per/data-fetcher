// Regression tests: different page destinations must preserve explicit export intent.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const code = fs.readFileSync("userscripts/goraggio-export.user.js", "utf8");

function exercise(pathname, hash, memory = {}, time = 1_000_000) {
  const elements = [];
  const status = { textContent: "" };
  const controls = { appendChild(el) { elements.push(el); } };
  const close = { addEventListener() {} };
  const panel = {
    id: "", style: {},
    set innerHTML(_) {},
    querySelector(s) {
      return {"#df-status":status,"#df-controls":controls,"#df-close":close}[s];
    },
  };
  const document = {
    body: {appendChild(el) {elements.push(el);}},
    documentElement: {appendChild(el) {elements.push(el);}},
    createElement(tag) {
      if(tag==="section") return panel;
      return {
        style: {},
        textContent:"",
        addEventListener(){},
        appendChild(){},
      };
    },
    querySelectorAll() {return [];},
    querySelector(){return null;}
  };
  const sessionStorage = {
    getItem(k){return memory[k] || null;},
    setItem(k,v){memory[k]=v;}
  };
  const context={
    document, sessionStorage,
    location:{
      origin:"https://daidata.goraggio.com",
      pathname, hash, search:"?ps=S",
      href:"https://daidata.goraggio.com"+pathname+"?ps=S"+hash,
    },
    Date:class extends Date {static now(){return time;}},
    URL, URLSearchParams, Set, RegExp, JSON, console
  };
  vm.runInNewContext(code,context,{timeout:1000});
  return {active:elements.includes(panel), status:status.textContent, memory};
}
const memory={};
assert.equal(exercise("/100831/list","#df-export",memory).active,true,"model list starts");
assert.equal(exercise("/100831/unit_list","",memory,1_002_000).active,true,"model unit list after link");
assert.equal(exercise("/100831/detail","",memory,1_003_000).active,true,"detail follows site links");
assert.equal(exercise("/100831/all_list","#df-export",{}).active,true,"all list preserved");
assert.equal(exercise("/100831/detail","#df-export",{}).active,true,"direct unit preserved");
assert.equal(exercise("/100831/list","",{}).active,false,"direct site browsing untouched");
assert.equal(exercise("/100831/list","",memory,1_000_000+16*60*1000).active,false,"session expires");
assert.equal(exercise("/100983/unit_list","",memory).active,false,"shop-scoped intent");
assert.equal(exercise("/100831/terms","#df-export",memory).active,false,"consent excluded");
console.log("Userscripts navigation gate regression tests passed");
