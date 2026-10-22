import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import "./style.css";
import {useStudio} from './stores/studio';
const app=createApp(App);
const pinia=createPinia();
app.use(pinia);
app.config.errorHandler=(error)=>{
  useStudio(pinia).connectionError='操作未完成：'+String(error);
};
app.mount("#app");
