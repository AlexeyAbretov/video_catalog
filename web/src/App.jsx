import { Route, Routes } from "react-router-dom";
import { Catalog } from "./Catalog";
import { MoviePage } from "./MoviePage";
import { ServicePage } from "./ServicePage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Catalog />} />
      <Route path="/movie/:id" element={<MoviePage />} />
      <Route path="/service" element={<ServicePage />} />
    </Routes>
  );
}
